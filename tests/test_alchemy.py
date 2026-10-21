"""
Unit tests for Alchemy Formula Engine
"""

import unittest
from src.models.schemas import (
    GameMaterial, GameMaterialEffect, GameMaterialHiddenEffect,
    HabitatKey, ClimateKey, ElementKey, NatureKey, GradeKey,
    MainEffectKey, HiddenEffectKey
)
from src.alchemy.formula import (
    calculate_material_potency, simulate_alchemy_pill
)


class TestAlchemyFormula(unittest.TestCase):

    def setUp(self):
        # Nhân Sâm (Thổ, Ôn, Linh Phẩm)
        self.nhan_sam = GameMaterial(
            id="mat_nhan_sam",
            name_key="mat_nhan_sam_name",
            desc_key="mat_nhan_sam_desc",
            grade_key=GradeKey.LINH_PHAM,
            habitat_key=HabitatKey.NUI_CAO,
            climate_key=ClimateKey.BANG_HAN,
            element_key=ElementKey.THO,
            nature_key=NatureKey.VI_NHIET,
            base_potency=200,
            growth_years_range=(10, 500),
            main_effects=[
                GameMaterialEffect(effect_key=MainEffectKey.BOOST_MAX_VITALITY, weight=0.8),
                GameMaterialEffect(effect_key=MainEffectKey.REGEN_VITALITY, weight=0.6)
            ],
            hidden_effects=[
                GameMaterialHiddenEffect(effect_key=HiddenEffectKey.HAIR_LOSS, trigger_chance=0.1)
            ]
        )

        # Bạch Truật (Kim, Bình, Linh Phẩm) - Thổ sinh Kim!
        self.bach_truat = GameMaterial(
            id="mat_bach_truat",
            name_key="mat_bach_truat_name",
            desc_key="mat_bach_truat_desc",
            grade_key=GradeKey.LINH_PHAM,
            habitat_key=HabitatKey.CAO_NGUYEN,
            climate_key=ClimateKey.ON_HOA,
            element_key=ElementKey.KIM,
            nature_key=NatureKey.BINH,
            base_potency=150,
            growth_years_range=(3, 50),
            main_effects=[
                GameMaterialEffect(effect_key=MainEffectKey.RESTORE_VITALITY, weight=0.7)
            ],
            hidden_effects=[
                GameMaterialHiddenEffect(effect_key=HiddenEffectKey.LUMINESCENCE, trigger_chance=0.05)
            ]
        )

        # Thủy Tinh Thảo (Thủy, Đại Hàn, Huyền Phẩm) - Kim sinh Thủy!
        self.thuy_tinh_thao = GameMaterial(
            id="mat_thuy_tinh_thao",
            name_key="mat_thuy_tinh_thao_name",
            desc_key="mat_thuy_tinh_thao_desc",
            grade_key=GradeKey.HUYEN_PHAM,
            habitat_key=HabitatKey.BIEN_SAU,
            climate_key=ClimateKey.BANG_HAN,
            element_key=ElementKey.THUY,
            nature_key=NatureKey.DAI_HAN,
            base_potency=600,
            growth_years_range=(50, 1000),
            main_effects=[
                GameMaterialEffect(effect_key=MainEffectKey.RESTORE_ENERGY, weight=0.9)
            ],
            hidden_effects=[
                GameMaterialHiddenEffect(effect_key=HiddenEffectKey.MERIDIAN_BLOCK, trigger_chance=0.1)
            ]
        )

        # Hỏa Viêm Chi (Hỏa, Đại Nhiệt, Địa Phẩm) - Thủy khắc Hỏa!
        self.hoa_viem_chi = GameMaterial(
            id="mat_hoa_viem_chi",
            name_key="mat_hoa_viem_chi_name",
            desc_key="mat_hoa_viem_chi_desc",
            grade_key=GradeKey.DIA_PHAM,
            habitat_key=HabitatKey.NUI_LUA,
            climate_key=ClimateKey.HOA_NHIET,
            element_key=ElementKey.HOA,
            nature_key=NatureKey.DAI_NHIET,
            base_potency=2500,
            growth_years_range=(100, 2000),
            main_effects=[
                GameMaterialEffect(effect_key=MainEffectKey.BREAKTHROUGH, weight=1.0)
            ],
            hidden_effects=[
                GameMaterialHiddenEffect(effect_key=HiddenEffectKey.BERSERK, trigger_chance=0.2)
            ]
        )

    def test_potency_calculation(self):
        # Kiểm tra công thức dược lực: Base * (1 + log10(years)) * GradeMultiplier
        # Nhân sâm 100 năm: 200 * (1 + 2) * 2.5 = 1500
        p = calculate_material_potency(self.nhan_sam, years_growth=100)
        self.assertEqual(p, 1500.0)

        # Hỏa Viêm Chi 1000 năm: 2500 * (1 + 3) * 10 = 100,000
        p_fire = calculate_material_potency(self.hoa_viem_chi, years_growth=1000)
        self.assertEqual(p_fire, 100000.0)

    def test_masterpiece_pill(self):
        # Quân (Thổ - Nhân Sâm) -> Thần (Kim - Bạch Truật): Thổ sinh Kim -> Tương sinh!
        result = simulate_alchemy_pill(
            quan=self.nhan_sam,
            than=self.bach_truat,
            ta=self.bach_truat,
            su=self.nhan_sam
        )
        self.assertFalse(result.is_exploded)
        self.assertGreaterEqual(result.harmony_score, 1.0)
        self.assertGreater(result.final_potency, 0)

    def test_furnace_explosion_conflict(self):
        # Thủy Tinh Thảo (Thủy, Đại Hàn) vs Hỏa Viêm Chi (Hỏa, Đại Nhiệt)
        # Quân và Thần tương khắc trực tiếp và tính chất Đại Hàn vs Đại Nhiệt không có chất trung hòa
        result = simulate_alchemy_pill(
            quan=self.thuy_tinh_thao,
            than=self.hoa_viem_chi,
            ta=self.thuy_tinh_thao,
            su=self.hoa_viem_chi
        )
        self.assertTrue(result.is_exploded)
        self.assertEqual(result.harmony_score, 0.0)
        self.assertEqual(result.final_potency, 0.0)
        self.assertIn("Nổ Lò", result.status)


if __name__ == "__main__":
    unittest.main()

