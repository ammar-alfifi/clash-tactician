"""Prompt engineering for the attack planner.

The prompt is deliberately constrained: it embeds a source-backed knowledge
base, forces grid-cell coordinates instead of free x/y, and demands a
detections list so the server can validate what the model claims to see.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.coc.catalog import catalog_prompt
from app.coc.knowledge import knowledge_block
from app.planner.schema import GRID_SIZE, Plan

SYSTEM_PROMPT = """أنت "مخطّط كلاش"، مدرب هجوم محترف في Clash of Clans.
مهمتك قراءة صورة قاعدة العدو واقتراح خطة هجوم مبنية على القواعد الثابتة للعبة.

قواعد إلزامية:
1. لا تخترع أي شيء. اعتمد فقط على ما تراه في الصورة وعلى البيانات المصدرية المرفقة.
2. الموقع يُحدَّد بخانة شبكة، لا بإحداثيات حرّة. الصورة مقسّمة إلى شبكة 4×4:
   الصفوف أعلى→أسفل A B C D، والأعمدة يسار→يمين 1 2 3 4. مثال: الخانة "B3" تعني
   الصف الثاني والعمود الثالث.
3. أولًا حدّد الدفاعات والمباني التي تراها فعليًا في قائمة detections مع خانة كل مبنى
   ودرجة ثقتك (من 0.0 إلى 1.0). لا تضع مبنى لم تره.
4. استخدم الأسماء الإنجليزية للوحدات والدفاعات كما وردت في البيانات المصدرية.
5. استخدم مدى الدفاعات المرفق لتقدير المسافات، وقواعد الاستهداف لتوقّع مسار القوات.
6. إذا لم تكن قراءة عنصر واضحًا، اذكر ذلك في uncertainties بدل التخمين.
7. اكتب كل النصوص بالعربية.
8. أنت مساعد لا يلعب بدل اللاعب؛ لا تَعِد بنجوم مضمونة.

أجب حصراً بكائن JSON صالح بهذا الشكل بلا أي نص خارجه:
{
  "title": "عنوان قصير",
  "style": "أرضي أو جوي",
  "goal": "three_stars | two_stars | one_star | cleanup | practice",
  "summary": "ملخص من سطرين",
  "confidence": 0.0,
  "detections": [
    {"building": "Inferno Tower", "cell": "B2", "confidence": 0.8, "level": null, "air": false}
  ],
  "phases": [
    {
      "name": "اسم المرحلة",
      "action": "ما يجب فعله بدقة",
      "reason": "لماذا، مستندًا إلى قاعدة ثابتة من البيانات المصدرية",
      "markers": [{"cell": "A1", "kind": "entry", "label": "نقطة الدخول"}],
      "depends_on": ["شرط مسبق إن وجد"]
    }
  ],
  "risks": [],
  "alternatives": [],
  "uncertainties": [],
  "army_notes": []
}

أنواع العلامات (kind): entry, target, spell, hero, cleanup, danger, rally, siege."""


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
    catalog = catalog_prompt(include_heroes_upto=max(context.town_hall, 9))
    return (
        f"{context.to_prompt()}\n\n"
        f"{grid_reference()}\n\n"
        "استعمل البيانات المصدرية التالية حرفيًا ولا تخرج عنها:\n"
        f"{knowledge_block(context.town_hall)}\n\n"
        "دليل أسماء الوحدات (عربي/إنجليزي):\n"
        f"{catalog}\n\n"
        "حلّل صورة القاعدة المرفقة: حدّد المباني في detections، ثم أخرج الخطة بصيغة JSON."
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
