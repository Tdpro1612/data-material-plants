"""
Pydantic schemas and Enums for Game Herbal and Alchemy System.
Follows documents/game_herbal_system_design.md strictly.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class HabitatKey(str, Enum):
    DONG_BANG = "hab_dong_bang"
    NUI_CAO = "hab_nui_cao"
    CAO_NGUYEN = "hab_cao_nguyen"
    NUI_TUYET = "hab_nui_tuyet"
    NUI_LUA = "hab_nui_lua"
    VUC_SAU = "hab_vuc_sau"
    DAM_LAY = "hab_dam_lay"
    BIEN_SAU = "hab_bien_sau"
    SA_MAC = "hab_sa_mac"
    HANG_DONG = "hab_hang_dong"
    RUNG_NGUYEN_SINH = "hab_rung_nguyen_sinh"


class ClimateKey(str, Enum):
    BANG_HAN = "clim_bang_han"
    ON_HOA = "clim_on_hoa"
    HOA_NHIET = "clim_hoa_nhiet"
    AM_THAP = "clim_am_thap"
    KHO_HAN = "clim_kho_han"
    CHUONG_KHI = "clim_chuong_khi"
    LOI_VU = "clim_loi_vu"


class ElementKey(str, Enum):
    KIM = "elem_kim"
    MOC = "elem_moc"
    THUY = "elem_thuy"
    HOA = "elem_hoa"
    THO = "elem_tho"
    VO_TINH = "elem_vo_tinh"


class NatureKey(str, Enum):
    DAI_HAN = "nat_dai_han"
    VI_HAN = "nat_vi_han"
    BINH = "nat_binh"
    VI_NHIET = "nat_vi_nhiet"
    DAI_NHIET = "nat_dai_nhiet"


class GradeKey(str, Enum):
    PHAM_PHAM = "grade_pham_pham"
    LINH_PHAM = "grade_linh_pham"
    HUYEN_PHAM = "grade_huyen_pham"
    DIA_PHAM = "grade_dia_pham"
    THIEN_PHAM = "grade_thien_pham"


class MainEffectKey(str, Enum):
    RESTORE_VITALITY = "eff_restore_vitality"
    REGEN_VITALITY = "eff_regen_vitality"
    BOOST_MAX_VITALITY = "eff_boost_max_vitality"
    BODY_REFINING = "eff_body_refining"
    RESTORE_ENERGY = "eff_restore_energy"
    REGEN_ENERGY = "eff_regen_energy"
    BOOST_MAX_ENERGY = "eff_boost_max_energy"
    SPIRIT_FOCUS = "eff_spirit_focus"
    BREAKTHROUGH = "eff_breakthrough"
    DETOX = "eff_detox"


class HiddenEffectKey(str, Enum):
    HAIR_LOSS = "eff_hidden_hair_loss"
    MERIDIAN_BLOCK = "eff_hidden_meridian_block"
    VITAL_EXHAUST = "eff_hidden_vital_exhaust"
    BERSERK = "eff_hidden_berserk"
    LUMINESCENCE = "eff_hidden_luminescence"
    ENLIGHTENMENT = "eff_hidden_enlightenment"


# ==============================================================
# RAW BOTANY MODELS (Agent 1 Output)
# ==============================================================

class RawBotanyMaterial(BaseModel):
    common_name: str = Field(description="Tên gọi vị thuốc thông dụng")
    scientific_name: str = Field(description="Tên khoa học")
    habitat_raw: str = Field(description="Môi trường sinh trưởng tự nhiên ngoài đời thực")
    climate_raw: str = Field(description="Điều kiện khí hậu sinh trưởng thực tế")
    appearance_raw: str = Field(description="Mô tả chi tiết hình thái thực vật: thân, lá, rễ, hoa, cơ chế sinh trưởng")
    nature_raw: str = Field(description="Tính vị y học cổ truyền thực tế (Hàn, Lương, Bình, Ôn, Nhiệt...)")
    medicinal_uses_raw: List[str] = Field(description="Công dụng y học cổ truyền thực tế")
    toxicity_and_contraindications: str = Field(description="Độc tính, tác dụng phụ hoặc kiêng kỵ thực tế")
    growth_period_raw: str = Field(description="Thời gian sinh trưởng ngoài tự nhiên để thu hoạch")
    source_reference: str = Field(default="Dược Điển & Y Học Cổ Truyền", description="Tài liệu tham khảo")


class RawBotanyBatch(BaseModel):
    materials: List[RawBotanyMaterial] = Field(description="Danh sách thảo dược thô cào được")


# ==============================================================
# GAME MATERIAL MODELS (Agent 2 Output)
# ==============================================================

class GameMaterialEffect(BaseModel):
    effect_key: MainEffectKey = Field(description="Mã khóa công dụng chính")
    weight: float = Field(ge=0.1, le=1.0, description="Trọng số công dụng từ 0.1 đến 1.0")


class GameMaterialHiddenEffect(BaseModel):
    effect_key: HiddenEffectKey = Field(description="Mã khóa công dụng ẩn")
    trigger_chance: float = Field(ge=0.01, le=0.50, description="Tỷ lệ kích hoạt (0.01 đến 0.50)")


class GameMaterial(BaseModel):
    id: str = Field(pattern=r"^mat_[a-z0-9_]+$", description="Mã định danh duy nhất (ví dụ: mat_nhan_sam)")
    name_key: str = Field(description="Mã localization tên gọi (ví dụ: mat_nhan_sam_name)")
    desc_key: str = Field(description="Mã localization mô tả hình thái (ví dụ: mat_nhan_sam_desc)")
    grade_key: GradeKey = Field(description="Phẩm cấp dược liệu")
    habitat_key: HabitatKey = Field(description="Mã nơi sinh chuẩn")
    climate_key: ClimateKey = Field(description="Mã khí hậu chuẩn")
    element_key: ElementKey = Field(description="Mã ngũ hành chuẩn")
    nature_key: NatureKey = Field(description="Mã dược tính hàn nhiệt chuẩn")
    base_potency: int = Field(ge=1, description="Dược lực cơ sở")
    growth_years_range: List[int] = Field(min_length=2, max_length=2, description="Khoảng năm sinh trưởng [min_years, max_years]")
    main_effects: List[GameMaterialEffect] = Field(min_length=1, max_length=5, description="1 đến 5 công dụng chính")
    hidden_effects: List[GameMaterialHiddenEffect] = Field(min_length=1, max_length=3, description="1 đến 3 công dụng ẩn")

    @field_validator("growth_years_range")
    @classmethod
    def validate_years_range(cls, v: List[int]) -> List[int]:
        if v[0] < 1 or v[1] < v[0]:
            raise ValueError(f"growth_years_range invalid: min must be >= 1 and min <= max, got {v}")
        return v


class LocaleEntry(BaseModel):
    key: str = Field(description="Mã localization key (ví dụ: mat_nhan_sam_name)")
    value: str = Field(description="Văn bản tiếng Việt tương ứng")


class GameTransformerOutput(BaseModel):
    materials: List[GameMaterial]
    locale_entries: List[LocaleEntry] = Field(description="Danh sách các cặp key-value bản dịch tiếng Việt")
