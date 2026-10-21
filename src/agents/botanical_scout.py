"""
Agent 1: Botanical Scout
Collects and extracts authentic botanical and TCM data from sources.
Supports dynamic batching, strict alias-aware deduplication, exponential backoff, and incremental saving.
"""

import os
import re
import json
import time
from typing import List, Set, Tuple, Optional, Callable, Any
import frontmatter
from google import genai
from dotenv import load_dotenv

from src.models.schemas import RawBotanyBatch, RawBotanyMaterial

load_dotenv()


def load_agent_prompt(agent_path: str = ".agents/botanical_scout.md"):
    with open(agent_path, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)
    return post.metadata, post.content


def normalize_text(text: str) -> str:
    """Chuẩn hóa chuỗi text cơ bản."""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(clean.split())


def extract_herb_aliases(common_name: str, scientific_name: str = "") -> List[str]:
    """
    Bóc tách tất cả các bí danh, tên gọi khác, tên phụ và tên khoa học của một vị thuốc.
    Ví dụ: 'Kê Huyết Đằng / Cỏ Máu (Spatholobus suberectus)' ->
    ['kê huyết đằng', 'cỏ máu', 'spatholobus suberectus']
    """
    aliases = set()
    raw_texts = [common_name, scientific_name]

    for text in raw_texts:
        if not text:
            continue
        # Tách theo các ký tự phân cách thông dụng
        parts = re.split(r"[/;,|]", text)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Bóc nội dung trong ngoặc đơn và ngoài ngoặc đơn
            paren_matches = re.findall(r"\((.*?)\)", part)
            outside_paren = re.sub(r"\(.*?\)", "", part).strip()

            if outside_paren:
                clean_outside = normalize_text(outside_paren)
                if clean_outside:
                    aliases.add(clean_outside)

            for m in paren_matches:
                clean_m = normalize_text(m)
                if clean_m:
                    aliases.add(clean_m)

            clean_full_part = normalize_text(part)
            if clean_full_part:
                aliases.add(clean_full_part)

    return sorted(list(aliases))


def call_with_backoff(api_call_fn: Callable[[], Any], max_retries: int = 4, base_delay: float = 2.0) -> Any:
    """
    Gọi hàm API kèm cơ chế tự động thử lại (Retry with Exponential Backoff) khi gặp lỗi Rate Limit hoặc mạng.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return api_call_fn()
        except Exception as e:
            if attempt == max_retries:
                raise e
            wait_time = base_delay * (2 ** (attempt - 1))
            print(f"  [API Cảnh Báo] Gặp sự cố ('{e}'). Đang nghỉ và thử lại lần {attempt}/{max_retries} sau {wait_time:.1f}s...")
            time.sleep(wait_time)


def load_existing_raw_materials(raw_path: str = "outputs/raw/botany_raw.json") -> List[RawBotanyMaterial]:
    """Đọc danh sách thảo dược thô đã có trong hệ thống."""
    if not os.path.exists(raw_path):
        return []
    try:
        with open(raw_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            batch = RawBotanyBatch.model_validate(data)
            return batch.materials
    except Exception as e:
        print(f"[Cảnh báo] Lỗi khi đọc {raw_path}: {e}")
        return []


def save_raw_materials(materials: List[RawBotanyMaterial], raw_path: str = "outputs/raw/botany_raw.json"):
    """Lưu danh sách thảo dược thô vào file."""
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    batch = RawBotanyBatch(materials=materials)
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(batch.model_dump_json(indent=2))


def fetch_botanical_batch(
    client: genai.Client,
    model_name: str,
    system_instruction: str,
    batch_size: int,
    excluded_names: List[str]
) -> List[RawBotanyMaterial]:
    """Gọi Gemini API để lấy 1 batch thảo dược mới chưa có trong danh sách loại trừ."""
    exclude_text = "\n".join([f"- {name}" for name in excluded_names]) if excluded_names else "(Chưa có thảo dược nào)"

    prompt_user = f"""
    Hãy tìm kiếm và trích xuất thông tin thực tế trung thực của {batch_size} vị thảo dược / cây thuốc đông y khác nhau ở Việt Nam hoặc Châu Á.

    QUY TẮC BẮT BUỘC CHỐNG TRÙNG LẶP:
    TUYỆT ĐỐI KHÔNG chọn các cây thuốc đã có hoặc là tên gọi khác/tên khoa học của những cây trong danh sách sau:
    {exclude_text}

    YÊU CẦU:
    1. Đa dạng hóa các nhóm dược liệu: bổ khí, bổ huyết, thanh nhiệt, hóa thấp, khu phong, giải độc, ôn trung, hồi dương, chỉ huyết...
    2. Mô tả chi tiết hình thái thực vật (thân, lá, hoa, rễ củ, cơ chế sinh thái) ở appearance_raw.
    3. Xác định rõ môi trường sống ở habitat_raw và khí hậu ở climate_raw.
    4. Ghi rõ tính vị quy kinh thực tế ở nature_raw.
    5. Ghi rõ các công dụng y học thực tế ở medicinal_uses_raw.
    6. Ghi rõ độc tính, tác dụng phụ hoặc kiêng kỵ ở toxicity_and_contraindications.
    7. Ghi rõ thời gian sinh trưởng ở growth_period_raw.
    """

    def _execute():
        response = client.models.generate_content(
            model=model_name,
            contents=prompt_user,
            config=dict(
                system_instruction=system_instruction,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=RawBotanyBatch,
            )
        )
        return RawBotanyBatch.model_validate_json(response.text)

    batch_output = call_with_backoff(_execute)
    return batch_output.materials


def run_botanical_scout(
    mode: str = "fill",
    amount: int = 100,
    batch_size: int = 10,
    delay_between_batches: float = 2.0,
    raw_path: str = "outputs/raw/botany_raw.json"
) -> Tuple[List[RawBotanyMaterial], int, str]:
    """
    Điều phối Agent 1 cào dữ liệu thảo dược:
    - mode="fill": Cào cho đủ tổng số `amount` thảo dược (nếu đã có >= amount thì dừng ngay).
    - mode="add": Cào thêm `amount` thảo dược mới.
    
    Trả về: (toàn bộ danh sách thảo dược, số lượng mới cào được, trạng thái kết thúc)
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY không được tìm thấy trong .env!")

    client = genai.Client(api_key=api_key)
    metadata, system_instruction = load_agent_prompt()
    model_name = metadata.get("model", "gemini-2.5-flash")
    if "3.8" in model_name:
        model_name = "gemini-2.5-flash"

    # 1. Tải danh sách hiện có
    existing_materials = load_existing_raw_materials(raw_path)
    current_count = len(existing_materials)
    print(f"[Agent 1: Botanical Scout] Hiện trong kho dữ liệu thô đã có: {current_count} thảo dược.")

    # 2. Xác định số lượng cần cào thêm
    if mode.lower() == "fill":
        if current_count >= amount:
            msg = f"ĐÃ ĐỦ SỐ LƯỢNG: Hiện đã có {current_count}/{amount} thảo dược, không cần cào thêm."
            print(f"[Agent 1] {msg}")
            return existing_materials, 0, "ALREADY_FULL"
        needed = amount - current_count
        print(f"[Agent 1] Chế độ 'Cào cho đủ': Cần cào thêm {needed} thảo dược để đạt mốc {amount}.")
    else:  # mode == "add"
        needed = amount
        print(f"[Agent 1] Chế độ 'Cào thêm': Cần cào thêm {needed} thảo dược mới.")

    # 3. Xây dựng tập hợp nhận diện bí danh (Alias Signatures) chống trùng lặp
    known_signatures: Set[str] = set()
    excluded_names: List[str] = []

    for m in existing_materials:
        aliases = extract_herb_aliases(m.common_name, m.scientific_name)
        for alias in aliases:
            known_signatures.add(alias)
        excluded_names.append(f"{m.common_name} ({m.scientific_name})")

    newly_crawled_count = 0
    consecutive_empty_batches = 0
    max_retries = 3

    # 4. Vòng lặp chia batch
    while newly_crawled_count < needed:
        current_batch_size = min(batch_size, needed - newly_crawled_count)
        batch_index = (newly_crawled_count // batch_size) + 1
        total_batches_est = ((needed - 1) // batch_size) + 1
        
        print(f"\n[Agent 1] -> Đang cào Batch {batch_index}/{total_batches_est} (Mục tiêu batch này: {current_batch_size} cây)...")

        try:
            candidates = fetch_botanical_batch(
                client=client,
                model_name=model_name,
                system_instruction=system_instruction,
                batch_size=current_batch_size,
                excluded_names=excluded_names
            )
        except Exception as e:
            print(f"[Agent 1: Lỗi API khi gọi Batch {batch_index}]: {e}")
            consecutive_empty_batches += 1
            if consecutive_empty_batches >= max_retries:
                print("[Agent 1] Đã đạt giới hạn lỗi API/Token liên tiếp. Dừng cào và bảo lưu dữ liệu hiện tại.")
                return existing_materials, newly_crawled_count, "ERROR_OR_TOKEN_LIMIT"
            continue

        # Lọc chống trùng lặp bằng tập bí danh (Aliases Matching)
        added_in_this_batch = 0
        for cand in candidates:
            cand_aliases = extract_herb_aliases(cand.common_name, cand.scientific_name)
            
            # Kiểm tra xem có bất kỳ bí danh nào trùng với kho đã có hay không
            is_duplicate = any(alias in known_signatures for alias in cand_aliases)
            if is_duplicate:
                print(f"  [Bỏ qua trùng lặp bí danh]: {cand.common_name} ({cand.scientific_name})")
                continue

            # Thảo dược hoàn toàn mới
            for alias in cand_aliases:
                known_signatures.add(alias)
            excluded_names.append(f"{cand.common_name} ({cand.scientific_name})")
            
            existing_materials.append(cand)
            newly_crawled_count += 1
            added_in_this_batch += 1

            if newly_crawled_count >= needed:
                break

        print(f"[Agent 1] Batch {batch_index} thu nhận: +{added_in_this_batch} thảo dược mới. (Tiến độ: {newly_crawled_count}/{needed})")

        # Lưu dữ liệu thô ngay lập tức sau mỗi batch (Incremental save)
        save_raw_materials(existing_materials, raw_path)

        if added_in_this_batch == 0:
            consecutive_empty_batches += 1
            if consecutive_empty_batches >= max_retries:
                print("[Agent 1] Không còn tìm thấy thảo dược mới chưa trùng lặp. Dừng cào.")
                return existing_materials, newly_crawled_count, "NO_MORE_DATA"
        else:
            consecutive_empty_batches = 0

        # Delay giữa các batch để tránh chạm giới hạn Rate Limit của API
        if newly_crawled_count < needed and delay_between_batches > 0:
            time.sleep(delay_between_batches)

    status = "COMPLETED" if newly_crawled_count >= needed else "PARTIAL"
    print(f"\n[Agent 1: Botanical Scout] Hoàn thành cào! Đã thêm +{newly_crawled_count} thảo dược mới. Tổng kho hiện tại: {len(existing_materials)} cây.")
    return existing_materials, newly_crawled_count, status
