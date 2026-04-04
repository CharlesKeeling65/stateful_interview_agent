import re


def strip_question_prefix(text: str) -> str:
    return re.sub(r"^\s*Q\d+\s*:\s*", "", text).strip()


def clean_generated_question(text: str, expected_turn_no: int) -> str:
    text = text.strip()

    # 只保留第一行，避免附带解释
    text = text.splitlines()[0].strip()

    # 去掉常见引导语
    text = re.sub(
        r"^(Sure|Certainly|Of course|Here is the next question)[:\-\s]*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # 去掉开头或整体包裹的 markdown 粗体标记，例如 **Q2:** ...
    text = text.replace("**", "").strip()
    text = re.sub(r"^\s*#+\s*", "", text).strip()

    # 去掉任意已有的题号前缀，避免重生成时出现 "Q19: Q20: ..."
    text = re.sub(
        r"^(?:(?:Q|Question)\s*\d+[:.\-\s]*)+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    text = re.sub(r"^\s*#+\s*", "", text).strip()

    # 统一把 "Question 2", "Q 2", "Q2." 等标准化成 "Q2: "
    text = re.sub(
        rf"^(Q\s*{expected_turn_no}|Question\s*{expected_turn_no})[:.\-\s]*",
        f"Q{expected_turn_no}: ",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # 如果前面出现了重复前缀，例如 "Q2: Q2: xxx"
    text = re.sub(
        rf"^(Q{expected_turn_no}:\s*)+",
        f"Q{expected_turn_no}: ",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # 如果还没有标准前缀，则补上
    if not re.match(rf"^Q{expected_turn_no}:\s+", text):
        text = f"Q{expected_turn_no}: {text}"

    # 再次清理可能出现的重复前缀
    text = re.sub(
        rf"^Q{expected_turn_no}:\s*Q{expected_turn_no}:\s*",
        f"Q{expected_turn_no}: ",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # 保证是问句
    if "?" not in text:
        text = text.rstrip(".") + "?"

    return text
