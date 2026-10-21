"""
Alchemy Formula Engine: Quân - Thần - Tá - Sứ, Ngũ Hành, Dược Tính & Dược Lực.
Strictly implements documents/game_herbal_system_design.md.
"""

import math
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from src.models.schemas import (
    GameMaterial, GradeKey, ElementKey, NatureKey, MainEffectKey, HiddenEffectKey
)

# Grade Multipliers
GRADE_MULTIPLIERS: Dict[GradeKey, float] = {
    GradeKey.PHAM_PHAM: 1.0,
    GradeKey.LINH_PHAM: 2.5,
    GradeKey.HUYEN_PHAM: 5.0,
    GradeKey.DIA_PHAM: 10.0,
    GradeKey.THIEN_PHAM: 25.0,
}

# Role Weights (Quân - Thần - Tá - Sứ)
ROLE_WEIGHTS = {
    "quan": 0.50,
    "than": 0.25,
    "ta": 0.15,
    "su": 0.10,
}

# Ngũ Hành Tương Sinh: Kim -> Thủy -> Mộc -> Hỏa -> Thổ -> Kim
ELEMENT_GENERATES: Dict[ElementKey, ElementKey] = {
    ElementKey.KIM: ElementKey.THUY,
    ElementKey.THUY: ElementKey.MOC,
    ElementKey.MOC: ElementKey.HOA,
    ElementKey.HOA: ElementKey.THO,
    ElementKey.THO: ElementKey.KIM,
}

# Ngũ Hành Tương Khắc: Kim -> Mộc -> Thổ -> Thủy -> Hỏa -> Kim
ELEMENT_OVERCOMES: Dict[ElementKey, ElementKey] = {
    ElementKey.KIM: ElementKey.MOC,
    ElementKey.MOC: ElementKey.THO,
    ElementKey.THO: ElementKey.THUY,
    ElementKey.THUY: ElementKey.HOA,
    ElementKey.HOA: ElementKey.KIM,
}


def calculate_material_potency(material: GameMaterial, years_growth: Optional[int] = None) -> float:
    """
    Tính dược lực thực tế của 1 vị thuốc căn cứ theo BasePotency, Số năm tuổi và Phẩm cấp.
    P = BasePotency * (1 + log10(max(1, years))) * GradeMultiplier
    """
    if years_growth is None:
        # Lấy mốc trung bình của khoảng sinh trưởng nếu không chỉ định cụ thể
        years_growth = (material.growth_years_range[0] + material.growth_years_range[1]) // 2

    years_clamped = max(1, years_growth)
    age_multiplier = 1.0 + math.log10(years_clamped)
    grade_multiplier = GRADE_MULTIPLIERS.get(material.grade_key, 1.0)
    
    return float(material.base_potency) * age_multiplier * grade_multiplier


class AlchemyPillResult(BaseModel):
    is_exploded: bool = Field(description="Có nổ lò hay không")
    status: str = Field(description="Trạng thái phẩm cấp đan dược (Cực Phẩm, Thượng Phẩm, Hạ Phẩm, Nổ Lò)")
    harmony_score: float = Field(description="Hệ số ngũ hành hòa hợp Phi")
    raw_potency: float = Field(description="Tổng dược lực thô trước khi nhân hệ số")
    final_potency: float = Field(description="Dược lực đầu ra cuối cùng của viên đan")
    primary_effect: Optional[str] = Field(default=None, description="Hiệu ứng cốt lõi do Quân dược quyết định")
    synergy_chain: List[str] = Field(default_factory=list, description="Phân tích tương tác ngũ hành và dược tính")
    cleansed_hidden_effects: List[str] = Field(default_factory=list, description="Các tác dụng phụ bị Tá dược triệt tiêu")
    retained_hidden_effects: List[str] = Field(default_factory=list, description="Các tác dụng phụ còn sót lại")


def simulate_alchemy_pill(
    quan: GameMaterial,
    than: GameMaterial,
    ta: GameMaterial,
    su: GameMaterial,
    years_map: Optional[Dict[str, int]] = None,
) -> AlchemyPillResult:
    """
    Mô phỏng luyện đan theo Cổ Phương Quân - Thần - Tá - Sứ kết hợp Ngũ Hành và Dược Tính.
    """
    years_map = years_map or {}
    
    # 1. Tính Dược Lực từng vị thuốc
    p_quan = calculate_material_potency(quan, years_map.get("quan"))
    p_than = calculate_material_potency(than, years_map.get("than"))
    p_ta = calculate_material_potency(ta, years_map.get("ta"))
    p_su = calculate_material_potency(su, years_map.get("su"))

    raw_potency = (
        p_quan * ROLE_WEIGHTS["quan"] +
        p_than * ROLE_WEIGHTS["than"] +
        p_ta * ROLE_WEIGHTS["ta"] +
        p_su * ROLE_WEIGHTS["su"]
    )

    synergy_chain: List[str] = []
    is_exploded = False
    harmony_score = 1.0
    status = "Thượng Phẩm (Bình Hòa)"

    # 2. Kiểm tra Xung Khắc Dược Tính Hàn Nhiệt Cực Đoan
    natures = [quan.nature_key, than.nature_key, ta.nature_key, su.nature_key]
    has_extreme_cold = NatureKey.DAI_HAN in natures
    has_extreme_heat = NatureKey.DAI_NHIET in natures
    has_neutral = NatureKey.BINH in [ta.nature_key, su.nature_key]

    if has_extreme_cold and has_extreme_heat:
        if not has_neutral:
            is_exploded = True
            harmony_score = 0.0
            status = "Nổ Lò (Đại Hàn chạm trán Đại Nhiệt không có chất Bình Hòa điều giải)"
            synergy_chain.append("Xung đột dược tính cực đoan: Đại Hàn vs Đại Nhiệt -> Áp suất lò quá tải!")
        else:
            synergy_chain.append("Dược tính Đại Hàn và Đại Nhiệt được Tá/Sứ Dược Bình Hòa trung hòa.")

    # 3. Kiểm tra Ngũ Hành Tương Sinh / Tương Khắc giữa Quân và Thần
    elem_quan = quan.element_key
    elem_than = than.element_key
    elem_ta = ta.element_key
    elem_su = su.element_key

    # Xung khắc trực tiếp giữa Quân và Thần
    is_conflict_quan_than = (
        ELEMENT_OVERCOMES.get(elem_quan) == elem_than or
        ELEMENT_OVERCOMES.get(elem_than) == elem_quan
    )

    if not is_exploded and is_conflict_quan_than:
        # Kiểm tra xem Sứ hoặc Tá có đóng vai trò cầu nối tương sinh hay không
        # Ví dụ: Thủy khắc Hỏa, nhưng có Mộc: Thủy sinh Mộc, Mộc sinh Hỏa -> Hóa giải
        mediator_found = False
        for mediator in [elem_su, elem_ta]:
            if (ELEMENT_GENERATES.get(elem_quan) == mediator and ELEMENT_GENERATES.get(mediator) == elem_than) or \
               (ELEMENT_GENERATES.get(elem_than) == mediator and ELEMENT_GENERATES.get(mediator) == elem_quan):
                mediator_found = True
                break
        
        if mediator_found:
            harmony_score = 0.6
            status = "Hạ Phẩm (Ngũ hành có xung khắc nhưng Sứ/Tá dược đã kịp thời hòa giải)"
            synergy_chain.append(f"Quân ({elem_quan.value}) và Thần ({elem_than.value}) tương khắc, nhưng đã được cầu nối chuyển hóa.")
        else:
            is_exploded = True
            harmony_score = 0.0
            status = f"Nổ Lò (Quân [{elem_quan.value}] và Thần [{elem_than.value}] tương khắc gay gắt không có dược dẫn trung hòa)"
            synergy_chain.append(f"Ngũ hành tương khắc trực tiếp: {elem_quan.value} vs {elem_than.value} -> Nổ Lò!")

    # 4. Kiểm tra Chuỗi Tương Sinh Hoàn Hảo (Liên Hoàn Sinh -> Cực Phẩm)
    if not is_exploded and harmony_score == 1.0:
        is_continuous_gen = (
            ELEMENT_GENERATES.get(elem_quan) == elem_than and
            (ELEMENT_GENERATES.get(elem_than) == elem_ta or elem_ta == ElementKey.VO_TINH)
        )
        if is_continuous_gen:
            harmony_score = 1.5
            status = "Cực Phẩm (Ngũ Hành Tương Sinh Liên Hoàn - Đan Văn Phát Sáng)"
            synergy_chain.append(f"Tương sinh liên hoàn: {elem_quan.value} -> {elem_than.value} -> {elem_ta.value}!")

    # 5. Xử lý Tác Dụng Phụ (Công dụng ẩn)
    # Tá dược sẽ triệt tiêu hoặc giảm thiểu hiệu ứng phụ có hại
    cleansed: List[str] = []
    retained: List[str] = []

    # Thu thập toàn bộ công dụng ẩn từ Quân và Thần
    target_hidden = []
    for eff in (quan.hidden_effects + than.hidden_effects):
        target_hidden.append(eff.effect_key.value)

    # Tá dược có phẩm cấp càng cao thì triệt tiêu càng nhiều debuff
    ta_grade_power = GRADE_MULTIPLIERS.get(ta.grade_key, 1.0)
    for hidden_key in target_hidden:
        if ta_grade_power >= 2.5 or harmony_score >= 1.5:
            cleansed.append(hidden_key)
        else:
            retained.append(hidden_key)

    primary_effect = quan.main_effects[0].effect_key.value if quan.main_effects else None
    final_potency = 0.0 if is_exploded else (raw_potency * harmony_score)

    return AlchemyPillResult(
        is_exploded=is_exploded,
        status=status,
        harmony_score=harmony_score,
        raw_potency=round(raw_potency, 2),
        final_potency=round(final_potency, 2),
        primary_effect=primary_effect,
        synergy_chain=synergy_chain,
        cleansed_hidden_effects=list(set(cleansed)),
        retained_hidden_effects=list(set(retained)),
    )

