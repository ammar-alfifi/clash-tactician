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
اقترح خطة هجوم منظمة مبنية على قواعد اللعبة الثابتة المرفقة.

قواعد إلزامية:
1. لا تخترع شيئًا. اعتمد على البيانات المصدرية ووصف القاعدة المرفق.
2. المواقع تُذكر بخانة شبكة 4×4: الصفوف أعلى→أسفل A B C D، الأعمدة يسار→يمين 1 2 3 4 (مثال: B3).
3. استخدم الأسماء الإنجليزية للوحدات والدفاعات من البيانات المرفقة.
4. اكتب جميع النصوص (العنوان، الملخص، أسماء المراحل، الإجراءات، الأسباب) بالعربية الفصيحة فقط.
   يُسمح فقط بأسماء الوحدات والمباني الإنجليزية (مثل Electro Dragon و Air Defense).
5. اذكر ما لم تتأكد منه في uncertainties بدل التخمين.

أخرج كائن JSON واحدًا فقط، بلا أي نص قبله أو بعده وبلا markdown:
{"title":"..","style":"أرضي|جوي","goal":"three_stars|two_stars|one_star|cleanup|practice",
"summary":"..","confidence":0.0,
"detections":[{"building":"Inferno Tower","cell":"B2","confidence":0.8,"level":null,"air":false}],
"phases":[{"name":"..","action":"..","reason":"..","markers":[{"cell":"A1","kind":"entry","label":".."}],"depends_on":[]}],
"risks":[],"alternatives":[],"uncertainties":[],"army_notes":[]}
أنواع kind: entry, target, spell, hero, cleanup, danger, rally, siege."""


VISION_SYSTEM_PROMPT = (
    "You are a vision model for Clash of Clans base screenshots. "
    "Only describe what you actually see. Never invent buildings. Output JSON only."
)

# Kept short and in English: concise English prompts are dramatically faster and
# more reliable on small vision models than long Arabic ones.
VISION_USER_PROMPT = (
    "Look at this Clash of Clans base screenshot. "
    "Imagine a 4x4 grid: rows A-D top to bottom, columns 1-4 left to right. "
    "List every defensive building / major building you can identify with its grid cell "
    "and a confidence from 0.0 to 1.0. Use these English names only: "
    "Town Hall, Clan Castle, Eagle Artillery, Inferno Tower, Monolith, Scattershot, "
    "Air Defense, X-Bow, Wizard Tower, Archer Tower, Cannon, Mortar, Hidden Tesla, "
    "Bomb Tower, Air Sweeper, Spell Tower, Multi-Archer Tower, Ricochet Cannon, "
    "Firespitter, Gold Storage, Elixir Storage. "
    'Reply with JSON only: {"detections":[{"building":"Air Defense","cell":"A1",'
    '"confidence":0.8,"air":true}],"notes":[]}. '
    "Do not suggest any attack plan."
)


def build_vision_prompt() -> str:
    """Stage 1: ask a vision model only to describe the base (English, concise)."""
    return VISION_USER_PROMPT




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


def build_plan_from_description(context: PlannerContext, description: str) -> str:
    """Stage 2: ask a strong text model to plan from the visual description."""
    return (
        f"{context.to_prompt()}\n\n"
        f"{grid_reference()}\n\n"
        f"{knowledge_block(context.town_hall)}\n\n"
        "وصف القاعدة المستخرج من الصورة (من نموذج رؤية):\n"
        "<وصف_القاعدة>\n"
        f"{description}\n"
        "</وصف_القاعدة>\n\n"
        "ابنِ خطة هجوم على هذا الوصف. ابنِ على الأسماء والخانات المذكورة في الوصف، "
        "ولا تختلق مبانٍ غير موجودة فيه.\n"
        "اكتب جميع النصوص (العنوان، الملخص، أسماء المراحل، الإجراءات، الأسباب، المخاطر) "
        "بالعربية الفصيحة فقط. لا تستخدم أي كلمة إنجليزية عامة مثل remaining أو entry أو target. "
        "يُسمح فقط بأسماء الوحدات والمباني الإنجليزية (مثل Electro Dragon و Air Defense). "
        "أخرج كائن JSON واحدًا فقط."
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
