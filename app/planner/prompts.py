"""Prompt engineering for the attack planner.

The prompt is deliberately constrained: it embeds a source-backed knowledge
base, forces grid-cell coordinates instead of free x/y, and demands a
detections list so the server can validate what the model claims to see.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.coc.knowledge import knowledge_block
from app.planner.schema import GRID_SIZE, Plan

SYSTEM_PROMPT = """أنت "مخطّط كلاش"، مدرب هجوم في Clash of Clans.
اقرأ صورة القاعدة واقترح خطة هجوم مبنية على القواعد الثابتة المرفقة.

قواعد إلزامية:
1. لا تخترع شيئًا. اعتمد فقط على ما تراه في الصورة وعلى البيانات المصدرية.
2. أحدد المواقع بخانة شبكة 4×4: الصفوف أعلى→أسفل A B C D، الأعمدة يسار→يمين 1 2 3 4 (مثال: B3).
3. ابدأ بقائمة detections للمباني التي تراها فعلًا مع خانة كل مبنى وثقتك (0.0-1.0).
4. استخدم الأسماء الإنجليزية للوحدات والدفاعات من البيانات المرفقة.
5. اذكر ما لم تتأكد منه في uncertainties بدل التخمين.
6. اكتب النصوص بالعربية.

أخرج كائن JSON واحدًا فقط، بلا أي نص قبله أو بعده وبلا markdown:
{"title":"..","style":"أرضي|جوي","goal":"three_stars|two_stars|one_star|cleanup|practice",
"summary":"..","confidence":0.0,
"detections":[{"building":"Inferno Tower","cell":"B2","confidence":0.8,"level":null,"air":false}],
"phases":[{"name":"..","action":"..","reason":"..","markers":[{"cell":"A1","kind":"entry","label":".."}],"depends_on":[]}],
"risks":[],"alternatives":[],"uncertainties":[],"army_notes":[]}
أنواع kind: entry, target, spell, hero, cleanup, danger, rally, siege."""


@dataclass
class PlannerContext:
    town_hall: int
    goal_label: str
    army: str = ""
    player_name: str = ""
    notes: str = ""
    hero_info: str = ""
    battle_type: str = "حرب"

    def to_prompt(self) -> str:
        lines = [
            f"نوع المعركة: {self.battle_type}",
            f"هدف الهجوم: {self.goal_label}",
            f"مستوى قاعة المدينة للاعب: {self.town_hall or 'غير محدد'}",
        ]
        if self.player_name:
            lines.append(f"اسم اللاعب: {self.player_name}")
        if self.hero_info:
            lines.append(f"الأبطال: {self.hero_info}")
        if self.army:
            lines.append(f"التشكيلة المتوفرة: {self.army}")
        if self.notes:
            lines.append(f"ملاحظات إضافية: {self.notes}")
        return "\n".join(lines)


def grid_reference() -> str:
    rows = "، ".join(
        f"{chr(ord('A') + r)} = الشريط {r + 1} من أعلى"
        for r in range(GRID_SIZE)
    )
    cols = "، ".join(f"{c + 1} = العمود {c + 1} من يسار" for c in range(GRID_SIZE))
    return f"الشبكة {GRID_SIZE}×{GRID_SIZE}: الصفوف {rows}. الأعمدة {cols}."


def build_user_prompt(context: PlannerContext) -> str:
    return (
        f"{context.to_prompt()}\n\n"
        f"{grid_reference()}\n\n"
        f"{knowledge_block(context.town_hall)}\n\n"
        "حلّل صورة القاعدة المرفقة: حدّد المباني في detections ثم أخرج كائن JSON واحدًا فقط."
    )


def build_refine_prompt(plan: Plan, instruction: str, context: PlannerContext) -> str:
    return (
        "هذه خطة هجوم حالية بصيغة JSON:\n"
        f"{plan.to_json()}\n\n"
        f"تعليمات التعديل: {instruction}\n\n"
        f"سياق اللاعب:\n{context.to_prompt()}\n\n"
        "استعمل نفس البيانات المصدرية وقواعد الشبكة نفسها. أعد الخطة كاملة بعد التعديل "
        "بنفس صيغة JSON، محافظًا على detections وما هو صحيح، ومغيّرًا ما طُلب فقط."
    )
