"""
Hệ thống Xây Dựng Dữ Liệu Game Thảo Dược & Mô Phỏng Đan Đạo.
Điểm vào chính (CLI & Interactive Interface) điều phối Pipeline Đa Agent.
"""

import os
import sys
import argparse
from dotenv import load_dotenv

from src.agents.botanical_scout import load_existing_raw_materials
from src.pipeline import run_pipeline

load_dotenv()


def get_user_preferences():
    """Hỏi tùy chọn tương tác nếu người dùng không truyền tham số qua CLI."""
    current_count = len(load_existing_raw_materials())
    print("\n" + "=" * 60)
    print("   HỆ THỐNG AGENT THẢO DƯỢC & ĐAN ĐẠO (MULTI-AGENT)")
    print("=" * 60)
    print(f"📊 Kho dữ liệu thô hiện tại đang có: {current_count} thảo dược.\n")
    print("Vui lòng chọn chế độ hoạt động:")
    print("  [1] Cào cho ĐỦ số lượng mục tiêu (Ví dụ: đã có {0}, nhập 100 -> cào thêm {1})".format(current_count, max(0, 100 - current_count)))
    print("  [2] Cào THÊM số lượng chỉ định (Ví dụ: đã có {0}, nhập 50 -> cào thêm 50 mới)".format(current_count))
    print(f"  [3] ĐỒNG BỘ RULE MỚI: Game hóa lại toàn bộ {current_count} thảo dược đã cào")
    
    try:
        choice = input("\nNhập lựa chọn (1, 2 hoặc 3) [Mặc định: 1]: ").strip()
    except KeyboardInterrupt:
        print("\n\n[Đã hủy bỏ thao tác]")
        sys.exit(0)
    except EOFError:
        choice = "1"

    if choice == "3":
        return "fill", 0, 10, True

    mode = "add" if choice == "2" else "fill"
    prompt_label = "mục tiêu tổng số cần đạt" if mode == "fill" else "cần cào thêm"
    default_val = 100
    try:
        amount_input = input(f"Nhập số lượng thảo dược ({prompt_label}) [Mặc định: {default_val}]: ").strip()
        amount = int(amount_input) if amount_input else default_val
    except KeyboardInterrupt:
        print("\n\n[Đã hủy bỏ thao tác]")
        sys.exit(0)
    except (ValueError, EOFError):
        amount = default_val

    return mode, amount, 10, False


def main():
    parser = argparse.ArgumentParser(description="Hệ thống Agent Xây dựng Dữ liệu Thảo dược & Đan đạo")
    parser.add_argument("--mode", choices=["fill", "add"], default=None, help="Chế độ: 'fill' (cào cho đủ) hoặc 'add' (cào thêm)")
    parser.add_argument("--amount", "--count", type=int, default=None, help="Số lượng thảo dược")
    parser.add_argument("--batch-size", type=int, default=10, help="Số lượng mỗi batch (mặc định: 10)")
    parser.add_argument("--retransform", action="store_true", help="Đồng bộ lại Rule mới cho toàn bộ dữ liệu đã cào")

    args = parser.parse_args()

    if args.retransform:
        mode = "fill"
        amount = 0
        batch_size = args.batch_size
        force_retransform = True
    elif args.mode and args.amount is not None:
        mode = args.mode
        amount = args.amount
        batch_size = args.batch_size
        force_retransform = False
    else:
        # Nếu chạy trực tiếp không truyền tham số, vào giao diện tương tác
        if sys.stdin.isatty():
            mode, amount, batch_size, force_retransform = get_user_preferences()
        else:
            mode = args.mode or "fill"
            amount = args.amount or 100
            batch_size = args.batch_size
            force_retransform = False

    try:
        run_pipeline(
            mode=mode,
            amount=amount,
            batch_size=batch_size,
            force_retransform=force_retransform
        )
    except KeyboardInterrupt:
        print("\n\n[Đã dừng chương trình theo yêu cầu người dùng]")
        sys.exit(0)
    except Exception as e:
        print(f"\n[Lỗi Hệ Thống]: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
