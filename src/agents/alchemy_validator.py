"""
Agent 3: Alchemy Simulator & QA Validator
Validates schema integrity, 100% localization parity, and simulates alchemy recipes.
Prompt & Rules defined in .agents/alchemy_validator.md.
"""

import os
import json
from typing import List, Dict, Any, Tuple
from pydantic import ValidationError

from src.models.schemas import GameMaterial
from src.alchemy.formula import simulate_alchemy_pill, AlchemyPillResult


def run_alchemy_validator(
    materials_path: str = "outputs/processed/materials.json",
    locale_path: str = "outputs/locales/vi.json",
    report_output_path: str = "outputs/processed/qa_report.json"
) -> Dict[str, Any]:
    """
    Thực hiện kiểm chuẩn dữ liệu, đối soát bản dịch và mô phỏng luyện đan.
    """
    print("[Agent 3: QA & Alchemy Validator] Bắt đầu kiểm chuẩn hệ thống...")

    # 1. Đọc dữ liệu
    if not os.path.exists(materials_path):
        raise FileNotFoundError(f"Không tìm thấy file {materials_path}!")
    if not os.path.exists(locale_path):
        raise FileNotFoundError(f"Không tìm thấy file {locale_path}!")

    with open(materials_path, "r", encoding="utf-8") as f:
        raw_materials = json.load(f)

    with open(locale_path, "r", encoding="utf-8") as f:
        locale_data = json.load(f)

    # 2. Schema Validation (Pydantic)
    validated_materials: List[GameMaterial] = []
    schema_errors = []

    for idx, item in enumerate(raw_materials):
        try:
            mat = GameMaterial.model_validate(item)
            validated_materials.append(mat)
        except ValidationError as e:
            schema_errors.append({"index": idx, "id": item.get("id"), "error": str(e)})

    # 3. Localization Parity Check (100% Key Check)
    missing_keys = []
    checked_keys = set()

    for mat in validated_materials:
        keys_to_check = [
            mat.name_key,
            mat.desc_key,
            mat.grade_key.value,
            mat.habitat_key.value,
            mat.climate_key.value,
            mat.element_key.value,
            mat.nature_key.value,
        ]
        for eff in mat.main_effects:
            keys_to_check.append(eff.effect_key.value)
        for h_eff in mat.hidden_effects:
            keys_to_check.append(h_eff.effect_key.value)

        for k in keys_to_check:
            checked_keys.add(k)
            if k not in locale_data:
                missing_keys.append({"material_id": mat.id, "missing_key": k})

    parity_rate = 1.0 if not missing_keys else max(0.0, 1.0 - len(missing_keys) / len(checked_keys))

    # 4. Alchemy Simulation (Mô phỏng luyện đan thực tế)
    simulations = []
    if len(validated_materials) >= 4:
        # Trường hợp 1: Thử nghiệm bài thuốc phối hợp theo thứ tự
        quan = validated_materials[0]
        than = validated_materials[1]
        ta = validated_materials[2]
        su = validated_materials[3]

        sim1 = simulate_alchemy_pill(quan, than, ta, su)
        simulations.append({
            "name": f"Đan Phương Mẫu 1 ({quan.id} + {than.id} + {ta.id} + {su.id})",
            "result": sim1.model_dump()
        })

        # Tìm kiếm hoặc tạo thử nghiệm Nổ Lò (Conflict test)
        # Tìm 2 cây có tương khắc ngũ hành hoặc xung khắc hàn nhiệt
        conflict_found = False
        for i in range(len(validated_materials)):
            for j in range(len(validated_materials)):
                if i != j:
                    test_sim = simulate_alchemy_pill(
                        quan=validated_materials[i],
                        than=validated_materials[j],
                        ta=validated_materials[i],
                        su=validated_materials[j]
                    )
                    if test_sim.is_exploded:
                        simulations.append({
                            "name": f"Thử nghiệm Nổ Lò ({validated_materials[i].id} vs {validated_materials[j].id})",
                            "result": test_sim.model_dump()
                        })
                        conflict_found = True
                        break
            if conflict_found:
                break

        # Tìm kiếm thử nghiệm Cực Phẩm hoặc Thượng Phẩm
        for i in range(len(validated_materials)):
            for j in range(len(validated_materials)):
                if i != j:
                    test_sim = simulate_alchemy_pill(
                        quan=validated_materials[i],
                        than=validated_materials[j],
                        ta=validated_materials[(i+1) % len(validated_materials)],
                        su=validated_materials[(j+1) % len(validated_materials)]
                    )
                    if test_sim.harmony_score >= 1.0 and not test_sim.is_exploded:
                        simulations.append({
                            "name": f"Thử nghiệm Đan Dược Thành Công ({validated_materials[i].id} + {validated_materials[j].id})",
                            "result": test_sim.model_dump()
                        })
                        break
            if len(simulations) >= 3:
                break

    report = {
        "total_materials_evaluated": len(raw_materials),
        "valid_materials_count": len(validated_materials),
        "schema_pass_rate": 1.0 if not schema_errors else round(len(validated_materials) / len(raw_materials), 4),
        "schema_errors": schema_errors,
        "total_unique_keys_checked": len(checked_keys),
        "localization_missing_keys_count": len(missing_keys),
        "localization_parity_rate": round(parity_rate, 4),
        "missing_keys_detail": missing_keys,
        "alchemy_simulations": simulations
    }

    os.makedirs(os.path.dirname(report_output_path), exist_ok=True)
    with open(report_output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[Agent 3: QA & Alchemy Validator] Hoàn thành thẩm định! Báo cáo: {report_output_path}")
    print(f" -> Schema Pass Rate: {report['schema_pass_rate'] * 100}%")
    print(f" -> Localization Parity Rate: {report['localization_parity_rate'] * 100}%")
    print(f" -> Số ca mô phỏng Luyện đan: {len(simulations)}")

    return report

