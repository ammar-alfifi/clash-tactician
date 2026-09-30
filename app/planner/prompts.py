"""Prompt engineering for the attack planner."""

from __future__ import annotations

from dataclasses import dataclass

from app.coc.catalog import catalog_prompt
from app.planner.schema import Plan

SYSTEM_PROMPT = """أنت "مخطّط كلاش"، مدرب هجوم محترف في Clash of Clans بخبرة طويلة في حروب القبائل.
مهمتك تحليل صورة قاعدة العدو واقتراح خطة هجوم واقعية قابلة للتنفيذ بأسلوب اللاعب.

قواعد صارمة:
1. اعتمد فقط على ما تراه في الصورة وما يُذكر في بيانات اللاعب. لا تخترع مبانٍ أو مستويات.
2. أشر إلى درجة ثقتك بصدق، واذكر بوضوح ما لم تستطع قراءته من الصورة.
3. استخدم وحدات وتعاويذ وأبطالًا متاحة فعلًا لمستوى قاعة المدينة المذكور.
4. الإحداثيات نسبية من 0.0 إلى 1.0 بالنسبة للصورة، والنقطة (0,0) أعلى اليسار.
5. اقترح 3 إلى 5 مراحل فقط، كل مرحلة عملية ومترابطة زمنيًا.
6. أنت مساعد لا يلعب بدل اللاعب، والنتيجة تعتمد على التنفيذ؛ لا تَعِد بنجوم مضمونة.
7. اكتب كل النصوص بالعربية.

أجب حصراً بكائن JSON صالح بهذا الشكل بلا أي نص خارجه:
{
  "title": "عنوان قصير للخطة",
  "goal": "three_stars | two_stars | one_star | cleanup | practice",
  "summary": "ملخص من سطرين لاستراتيجية الخطة",
  "confidence": 0.0,
  "phases": [
    {
      "name": "اسم المرحلة",
      "action": "ما يجب فعله بدقة",
      "reason": "لماذا هذا القرار",
      "markers": [{"x": 0.5, "y": 0.4, "kind": "entry", "label": "نقطة الدخول"}],
      "depends_on": ["شرط مسبق إن وجد"]
    }
  ],
  "risks": ["الخطر الرئيسي"],
  "alternatives": ["خطة بديلة عند فشل مسار"],
  "uncertainties": ["ما لم يتضح من الصورة"],
  "army_notes": ["ملاحظة عن التشكيلة أو التعزيزات"]
}

أنواع العلامات (kind) المسموحة: entry, target, spell, hero, cleanup, danger, rally, siege."""


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
        lines.append("")
        lines.append("انظر إلى صورة القاعدة المرفقة وحلّلها ثم أخرج الخطة بصيغة JSON المطلوبة.")
        return "\n".join(lines)


def build_user_prompt(context: PlannerContext) -> str:
    catalog = catalog_prompt(include_heroes_upto=max(context.town_hall, 9))
    return (
        f"{context.to_prompt()}\n\n"
        "مرجع الأسماء العربية للوحدات (استخدم الاسم العربي أو الإنجليزي فقط من هذه القائمة):\n"
        f"{catalog}"
    )


def build_refine_prompt(plan: Plan, instruction: str, context: PlannerContext) -> str:
    return (
        "هذه خطة هجوم حالية بصيغة JSON:\n"
        f"{plan.to_json()}\n\n"
        f"التعليمات: {instruction}\n\n"
        f"سياق اللاعب:\n{context.to_prompt()}\n\n"
        "أعد الخطة كاملة بعد التعديل بنفس صيغة JSON، مع الحفاظ على ما هو صحيح وتغيير ما طُلب فقط."
    )
