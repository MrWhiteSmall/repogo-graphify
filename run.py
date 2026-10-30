"""RepoGo 原创练习入口：调用固定版本 Graphify，不安装集成或 Git hooks。"""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

COMMIT = "0a8cd4e1e342235fe53e881fb5d591bf0460071f"
ARCHIVE_SHA256 = "5991696931ab1995f412dcd0fbb4b4caa96ac040e32bd8ba3996c8277f35e14f"
ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
UPSTREAM = RUNTIME / ("graphify-" + COMMIT)
WORK = RUNTIME / "workspace"
RESULTS = RUNTIME / "results"
ENV = dict(os.environ, GRAPHIFY_BACKEND="none", GRAPHIFY_QUERY_LOG_DISABLE="1",
           UV_CACHE_DIR=str(RUNTIME / "uv-cache"), UV_PYTHON_DOWNLOADS="never")


def execute(argv, cwd, name=None, timeout=180):
    command = [str(x) for x in argv]
    result = subprocess.run(command, cwd=cwd, env=ENV, text=True,
                            capture_output=True, timeout=timeout)
    if name:
        (RESULTS / (name + ".txt")).write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError("命令未完成，退出码 %s：\n%s\n%s" %
                           (result.returncode, result.stdout[-2000:], result.stderr[-2000:]))
    return result.stdout


def prepare_tool():
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("需要官方 uv（https://docs.astral.sh/uv/getting-started/installation/）；请先安装，不要关闭系统保护。")
    archive = RUNTIME / ("graphify-" + COMMIT + ".tar.gz")
    if not archive.exists():
        print("首次启动：从 Graphify 官方 GitHub 下载固定提交。", flush=True)
        request = urllib.request.Request(
            "https://codeload.github.com/Graphify-Labs/graphify/tar.gz/" + COMMIT,
            headers={"User-Agent": "RepoGo-original-practice/1"})
        with urllib.request.urlopen(request, timeout=90) as response:
            with archive.with_suffix(".part").open("wb") as target:
                shutil.copyfileobj(response, target)
        archive.with_suffix(".part").replace(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise RuntimeError("官方源码归档校验不一致，已停止；移出该缓存后从官方重试，不跳过校验。")
    if not (UPSTREAM / "pyproject.toml").exists():
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle.getmembers():
                destination = (RUNTIME / member.name).resolve()
                if not destination.is_relative_to(RUNTIME.resolve()) or not (
                    destination == UPSTREAM.resolve() or destination.is_relative_to(UPSTREAM.resolve())
                ) or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise RuntimeError("归档含不支持的路径或文件类型，已停止。")
            if hasattr(tarfile, "data_filter"):
                bundle.extractall(RUNTIME, filter="data")
            else:
                bundle.extractall(RUNTIME)  # Python 3.10：上方已逐项拒绝越界和链接。
    print("核对官方锁文件，安装到本目录 .runtime/；首次需要联网。", flush=True)
    execute([uv, "sync", "--frozen", "--no-dev", "--python", sys.executable], UPSTREAM, timeout=600)
    bindir = UPSTREAM / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    return bindir / ("graphify.exe" if os.name == "nt" else "graphify"), bindir / ("python.exe" if os.name == "nt" else "python")


def call_edges(graph):
    return [e for e in graph["links"] if e.get("relation") == "calls"]


def main():
    if sys.version_info < (3, 10):
        raise RuntimeError("需要 Python 3.10+；本期实测 3.12，当前 Python 版本过低。")
    RUNTIME.mkdir(exist_ok=True)
    WORK.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    cli, python = prepare_tool()
    for sample in (ROOT / "samples" / "before").glob("*.py"):
        shutil.copyfile(sample, WORK / sample.name)
    rows = []
    for stage, discount, amount in [("before", "standard_discount", 4000), ("after", "member_discount", 3600)]:
        if stage == "after":
            shutil.copyfile(ROOT / "samples" / "after-pricing.py", WORK / "pricing.py")
        app = ast.literal_eval(execute([python, "-B", "app.py"], WORK, stage + "-app").strip())
        if app != {"order_id": "demo-order", "total_cents": amount}:
            raise RuntimeError("样例运行结果不符，停止：" + str(app))
        execute([cli, "extract", ".", "--code-only", "--force", "--no-dedup", "--max-workers", "2"], WORK, stage + "-extract")
        graph_path = WORK / "graphify-out" / "graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        edges = call_edges(graph)
        expected = [("checkout_place_order", "pricing_quote_total", "checkout.py", "L6"),
                    ("pricing_quote_total", "policy_" + discount, "pricing.py", "L6")]
        for source, target, file, line in expected:
            matches = [e for e in edges if e["source"] == source and e["target"] == target]
            if len(matches) != 1 or any(matches[0].get(k) != v for k, v in {
                "source_file": file, "source_location": line, "confidence": "EXTRACTED"}.items()):
                raise RuntimeError("调用边或源码出处不符：" + source + " → " + target)
        other = "policy_" + ("member_discount" if stage == "before" else "standard_discount")
        if any(e["source"] == "pricing_quote_total" and e["target"] == other for e in edges):
            raise RuntimeError("发现不应存在的旧/新调用边，停止。")
        for verb, args in [
            ("path", ["place_order", discount]),
            ("query", ["quote_total discount", "--seed", "quote_total"]),
            ("explain", ["quote_total", "--all"]),
        ]:
            text = execute([cli, verb, *args, "--graph", graph_path], WORK, stage + "-" + verb)
            if discount not in text:
                raise RuntimeError("官方查询输出不含当前折扣函数：" + verb)
        shutil.copyfile(graph_path, RESULTS / (stage + "-graph.json"))
        rows.append({"stage": stage, "amount_cents": amount, "discount_function": discount,
                     "calls": [e for e in edges if e["source"] in ("checkout_place_order", "pricing_quote_total")],
                     "query_and_path_and_explain_passed": True})
        print("%s：%s 分；下单 → 算价 → %s；两条边及源码行号已核对。" % (stage, amount, discount), flush=True)
    report = {"passed": True, "version": "0.9.97", "commit": COMMIT,
              "llm_backend": "none", "rows": rows,
              "boundary": "原创5文件Python样例；静态关系+样例行为对照，非完整程序语义证明"}
    (RESULTS / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("练习通过：改动前后调用边已更新，应用结果 4000 → 3600 分。")
    print("报告：.runtime/results/；可编辑样例副本：.runtime/workspace/。再次运行会重置这5个练习文件。")
    print("扫描/查询已结束，无后台服务，无模型调用，无Git钩子安装。")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("未完成：" + str(error), file=sys.stderr)
        sys.exit(1)
