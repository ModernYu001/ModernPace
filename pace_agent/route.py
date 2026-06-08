"""Standalone Router demo: free-text request -> the right topic.

    python -m pace_agent.route "我想学分数"
    python -m pace_agent.route            # interactive

Shows how Pace maps natural language (any language) to a curriculum topic.
"""
import asyncio
import sys

from .demo import route_topic
from .curriculum import all_ready_topics


async def main() -> None:
    label_by_id = {t["id"]: f"{t['label']} ({t['grade']})" for t in all_ready_topics()}
    args = " ".join(sys.argv[1:]).strip()
    requests = [args] if args else None

    if requests is None:
        print("可选主题：", "; ".join(label_by_id.values()))
        try:
            while True:
                text = input("\n你想学什么？(Ctrl-C 退出) > ").strip()
                if not text:
                    continue
                topic = await route_topic(text)
                if topic is None:
                    print("  → 无匹配主题（暂未收录该主题）")
                else:
                    print(f"  → {topic}  |  {label_by_id.get(topic, topic)}")
        except (KeyboardInterrupt, EOFError):
            print()
            return

    topic = await route_topic(requests[0])
    if topic is None:
        print(f'"{requests[0]}"  →  无匹配主题（暂未收录该主题）')
    else:
        print(f'"{requests[0]}"  →  {topic}  |  {label_by_id.get(topic, topic)}')


if __name__ == "__main__":
    asyncio.run(main())
