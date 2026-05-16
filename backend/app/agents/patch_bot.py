import json, logging, re, uuid
from typing import TypedDict, Optional

log = logging.getLogger(__name__)
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.db.database import SessionLocal
from app.models.failure import Failure, FailureStatus
from app.models.patch import Patch, PatchStatus
from app.api.ws import broadcast

PLACEHOLDER_CODE = {
    "infinite_loop": 'def run_agent(q):\n    agent = create_react_agent(llm, tools)\n    # BUG: no max_iterations guard\n    return agent.invoke({"input": q})["output"]\n',
    "hallucination": 'def answer(q, ctx):\n    # BUG: no grounding instruction\n    return llm.invoke(f"{q}\\n\\nContext: {ctx}").content\n',
    "tool_misuse":   'def calc(expr):\n    # BUG: raw LLM string passed to tool\n    return CalculatorTool().run(expr)\n',
    "context_overflow": 'def summarize(doc):\n    # BUG: full document injected without chunking\n    return llm.invoke(f"Summarize:\\n\\n{doc}").content\n',
    "empty_response": 'def get_answer(q):\n    result = agent.invoke({"input": q})\n    # BUG: no fallback when output is missing\n    return result.get("output")\n',
}

def _extract_files_from_trace(trace: dict) -> list[str]:
    """Pull user-space Python file paths out of a LangSmith error/traceback."""
    error_text = trace.get("error", "") or ""
    # Also check nested child_runs for errors
    for child in trace.get("child_runs", []):
        error_text += "\n" + (child.get("error", "") or "")
    paths = re.findall(r'File ["\']([^"\']+\.py)["\']', error_text)
    # Drop stdlib and site-packages
    user_paths = [
        p.lstrip("./") for p in paths
        if "site-packages" not in p and not p.startswith("/usr") and not p.startswith("/opt")
    ]
    return list(dict.fromkeys(user_paths))  # deduplicate, preserve order

def _search_repo_for_agent_files(repo) -> list[str]:
    """Walk the repo tree and return likely agent entry-point files."""
    try:
        contents = repo.get_git_tree(repo.default_branch, recursive=True).tree
        candidates = []
        for item in contents:
            p = item.path
            if item.type == "blob" and p.endswith(".py"):
                name = p.split("/")[-1]
                if any(k in name for k in ("agent", "main", "chain", "graph", "bot")):
                    candidates.append(p)
        return candidates[:6]  # cap at 6 to avoid huge prompts
    except Exception:
        return []

class PatchState(TypedDict):
    failure_id: str
    failure_type: str
    root_cause: str
    trace_json: dict
    rejection_context: Optional[str]   # notes from a previous human rejection
    repo_code: Optional[str]
    file_path: Optional[str]
    file_patches: Optional[list]       # [{file_path, patched_code}] for multi-file fixes
    patch_type: Optional[str]
    original_code: Optional[str]
    patched_code: Optional[str]
    explanation: Optional[str]
    diff: Optional[str]
    pr_url: Optional[str]
    pr_number: Optional[int]
    branch_name: Optional[str]
    error: Optional[str]

async def fetch_code_node(state: PatchState) -> PatchState:
    if settings.github_token and settings.github_repo:
        try:
            from github import Github
            g = Github(settings.github_token)
            repo = g.get_repo(settings.github_repo)

            # 1. Paths extracted from the actual stack trace take priority
            trace_paths = _extract_files_from_trace(state.get("trace_json", {}))
            # 2. Fall back to heuristic scan of the repo tree
            repo_agent_files = _search_repo_for_agent_files(repo) if not trace_paths else []
            # 3. Static fallbacks last
            static_fallbacks = ["agent/agent.py", "agent/main_agent.py", "src/agent.py", "main.py"]
            candidate_paths = trace_paths + repo_agent_files + [
                p for p in static_fallbacks if p not in trace_paths
            ]

            code_parts: list[str] = []
            primary_file: str | None = None
            for path in candidate_paths[:4]:  # keep prompt size reasonable
                try:
                    f = repo.get_contents(path)
                    code_parts.append(f"# === {path} ===\n{f.decoded_content.decode()}")
                    if primary_file is None:
                        primary_file = path
                except Exception:
                    continue

            if code_parts:
                state["repo_code"] = "\n\n".join(code_parts)
                state["file_path"] = primary_file or candidate_paths[0]
                return state
        except Exception as e:
            log.error("fetch_code_node GitHub error: %s", e)
            state["error"] = str(e)

    # Offline / no GitHub token — use illustrative placeholder
    state["repo_code"] = PLACEHOLDER_CODE.get(
        state["failure_type"],
        f'def run_agent(q):\n    # {state["failure_type"]}\n    return agent.invoke({{"input": q}})["output"]\n',
    )
    state["file_path"] = "agent/main_agent.py"
    return state

def _parse_fix_response(text: str) -> dict | None:
    """Parse the structured LLM response using XML-style delimiters.
    Falls back to JSON extraction if delimiters are absent."""
    # Primary: delimited format (code never lives inside a JSON string)
    pc = re.search(r"<PATCHED_CODE>\n?([\s\S]*?)\n?</PATCHED_CODE>", text)
    if pc:
        pt_m = re.search(r"^PATCH_TYPE:\s*(.+)$", text, re.M)
        ex_m = re.search(r"^EXPLANATION:\s*(.+)$", text, re.M)
        df_m = re.search(r"<DIFF>\n?([\s\S]*?)\n?</DIFF>", text)
        fp_m = re.search(r"<FILE_PATCHES>\n?([\s\S]*?)\n?</FILE_PATCHES>", text)
        file_patches = []
        if fp_m:
            try:
                file_patches = json.loads(fp_m.group(1).strip())
            except Exception:
                pass
        return {
            "patch_type":  (pt_m.group(1).strip() if pt_m else "code_fix"),
            "patched_code": pc.group(1),
            "explanation":  (ex_m.group(1).strip() if ex_m else ""),
            "diff":         (df_m.group(1) if df_m else ""),
            "file_patches": file_patches,
        }

    # Fallback: JSON extraction with multi-pass sanitization
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    raw = m.group()
    for parser in (
        lambda s: json.loads(s, strict=False),
        lambda s: json.loads(_sanitize_json(s)),
        lambda s: json.loads(_sanitize_json(s), strict=False),
    ):
        try:
            return parser(raw)
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _sanitize_json(raw: str) -> str:
    """Escape literal newlines/tabs inside JSON string values via a simple state machine."""
    out, in_str, i = [], False, 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and in_str and i + 1 < len(raw):
            out.append(ch); out.append(raw[i + 1]); i += 2; continue
        if ch == '"':
            in_str = not in_str; out.append(ch)
        elif in_str and ch == "\n":
            out.append("\\n")
        elif in_str and ch == "\r":
            out.append("\\r")
        elif in_str and ch == "\t":
            out.append("\\t")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


async def generate_fix_node(state: PatchState) -> PatchState:
    llm = ChatGroq(model=settings.groq_model, temperature=0.2,
                   api_key=settings.groq_api_key)
    sys_msg = """You are TraceGuard AI Patch Bot. Reply in EXACTLY this format — no JSON, no markdown fences:

PATCH_TYPE: [prompt_rewrite|code_fix|guard_insertion]
EXPLANATION: [one sentence describing what changed and why]
<PATCHED_CODE>
[complete fixed code for the primary file, verbatim — no escaping needed]
</PATCHED_CODE>
<DIFF>
[unified diff]
</DIFF>
<FILE_PATCHES>
[JSON array of additional files that need changes: [{"file_path": "...", "patched_code": "..."}], or empty array []]
</FILE_PATCHES>"""

    rejection_note = ""
    if state.get("rejection_context"):
        rejection_note = (
            f"\n\nPREVIOUS FIX WAS REJECTED BY A HUMAN REVIEWER.\n"
            f"Reviewer notes: {state['rejection_context']}\n"
            f"You MUST address these concerns in the new fix."
        )

    human_msg = f"""Failure: {state['failure_type']}
Root cause: {state['root_cause']}
Primary file: {state.get('file_path')}{rejection_note}

Current code:
```python
{state.get('repo_code', '')}
```
Generate minimal targeted fix."""
    resp = await llm.ainvoke([SystemMessage(content=sys_msg),
                               HumanMessage(content=human_msg)])
    fix = _parse_fix_response(resp.content)
    if fix:
        state.update({"patch_type":    fix.get("patch_type", "code_fix"),
                      "original_code": state.get("repo_code", ""),
                      "patched_code":  fix.get("patched_code", ""),
                      "file_patches":  fix.get("file_patches") or [],
                      "explanation":   fix.get("explanation", ""),
                      "diff":          fix.get("diff", "")})
    else:
        log.error("generate_fix_node: could not parse LLM response: %s", resp.content[:400])
        state["error"] = "Could not parse fix from LLM"
    return state

async def open_pr_node(state: PatchState) -> PatchState:
    branch = f"traceguard/fix-{state['failure_type']}-{uuid.uuid4().hex[:8]}"
    state["branch_name"] = branch
    if settings.github_token and settings.github_repo and state.get("patched_code"):
        try:
            from github import Github, InputGitTreeElement
            g = Github(settings.github_token)
            repo = g.get_repo(settings.github_repo)
            base_branch = repo.default_branch
            base_sha = repo.get_branch(base_branch).commit.sha
            base_tree = repo.get_git_commit(base_sha).tree

            # Collect all file changes: primary + any additional files
            all_patches = [{"file_path": state.get("file_path"), "patched_code": state.get("patched_code", "")}]
            for fp in (state.get("file_patches") or []):
                if fp.get("file_path") and fp.get("patched_code"):
                    all_patches.append(fp)

            # Build a single Git tree with all changes — one clean commit
            tree_elements = [
                InputGitTreeElement(path=p["file_path"], mode="100644",
                                    type="blob", content=p["patched_code"])
                for p in all_patches if p.get("file_path")
            ]
            new_tree = repo.create_git_tree(tree_elements, base_tree)
            rejection_prefix = "fix(retry): " if state.get("rejection_context") else "fix: "
            commit = repo.create_git_commit(
                message=f"{rejection_prefix}TraceGuard auto-patch [{state['failure_type']}]",
                tree=new_tree,
                parents=[repo.get_git_commit(base_sha)]
            )
            repo.create_git_ref(f"refs/heads/{branch}", commit.sha)

            files_changed = ", ".join(p["file_path"] for p in all_patches if p.get("file_path"))
            rejection_section = ""
            if state.get("rejection_context"):
                rejection_section = (
                    f"\n\n---\n**Retry** - previous fix was rejected.\n"
                    f"**Reviewer notes addressed:** {state['rejection_context']}"
                )
            pr = repo.create_pull(
                title=f"[TraceGuard] Fix: {state['failure_type']}",
                body=(
                    f"**Auto-generated by TraceGuard AI**\n\n"
                    f"{state.get('explanation', '')}\n\n"
                    f"**Files changed:** `{files_changed}`"
                    f"{rejection_section}\n\n"
                    f"> Requires human approval."
                ),
                head=branch, base=base_branch)
            state["pr_url"] = pr.html_url
            state["pr_number"] = pr.number
        except Exception as e:
            log.error("open_pr_node GitHub error (repo=%s file=%s): %s",
                      settings.github_repo, state.get("file_path"), e)
            state["error"] = str(e)
            state["pr_url"] = f"https://github.com/{settings.github_repo}/pull/draft"
    else:
        missing = []
        if not settings.github_token: missing.append("GITHUB_TOKEN")
        if not settings.github_repo:  missing.append("GITHUB_REPO")
        if not state.get("patched_code"): missing.append("patched_code")
        log.warning("open_pr_node skipped - missing: %s", ", ".join(missing))
        state["pr_url"] = f"https://github.com/sandbox/repo/pull/{branch[-8:]}"
    return state

def build_patch_graph():
    g = StateGraph(PatchState)
    g.add_node("fetch_code",   fetch_code_node)
    g.add_node("generate_fix", generate_fix_node)
    g.add_node("open_pr",      open_pr_node)
    g.set_entry_point("fetch_code")
    g.add_edge("fetch_code",   "generate_fix")
    g.add_edge("generate_fix", "open_pr")
    g.add_edge("open_pr",      END)
    return g.compile()

async def run_patch_bot_async(failure_id: str, rejection_context: str = ""):
    db = SessionLocal()
    try:
        failure = db.query(Failure).filter(Failure.id == failure_id).first()
        if not failure:
            return
        graph = build_patch_graph()
        result = await graph.ainvoke({
            "failure_id": failure_id, "failure_type": failure.failure_type or "unknown",
            "root_cause": failure.root_cause_summary or "",
            "trace_json": failure.raw_trace or {},
            "rejection_context": rejection_context or None,
            "repo_code": None, "file_path": None, "file_patches": None,
            "patch_type": None, "original_code": None, "patched_code": None,
            "explanation": None, "diff": None, "pr_url": None,
            "pr_number": None, "branch_name": None, "error": None,
        })
        patch = Patch(failure_id=failure_id, patch_type=result.get("patch_type"),
                      file_path=result.get("file_path"),
                      original_code=result.get("original_code"),
                      patched_code=result.get("patched_code"),
                      explanation=result.get("explanation"), diff=result.get("diff"),
                      pr_url=result.get("pr_url"), pr_number=result.get("pr_number"),
                      branch_name=result.get("branch_name"),
                      status=PatchStatus.pr_opened if result.get("pr_url") else PatchStatus.pending)
        db.add(patch)
        failure.status = FailureStatus.patched
        db.commit()
        db.refresh(patch)
        await broadcast({"event": "patch_generated", "failure_id": failure_id,
                         "patch_id": patch.id, "pr_url": patch.pr_url})
    except Exception as e:
        log.error("run_patch_bot_async FAILED for %s: %s", failure_id, e, exc_info=True)
        await broadcast({"event": "patch_error", "failure_id": failure_id, "error": str(e)})
    finally:
        db.close()