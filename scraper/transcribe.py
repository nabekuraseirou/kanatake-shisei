"""
transcribe.py — ローカル Whisper 音声文字起こしツール

使い方:
    python scraper/transcribe.py audio.mp3
    python scraper/transcribe.py audio.mp3 --model medium --output result.txt
    python scraper/transcribe.py a.mp3 b.wav --model large

必要条件:
    pip install openai-whisper
    # または:
    pip install -r scraper/requirements-transcribe.txt

    # システム依存: ffmpeg がインストールされていること
    #   Ubuntu/Debian: sudo apt install ffmpeg
    #   macOS:         brew install ffmpeg
    #   Windows:       https://ffmpeg.org/download.html
"""

import argparse
import os
import sys


SUPPORTED_MODELS = ["tiny", "base", "small", "medium", "large"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="openai-whisper を使って音声ファイルを文字起こしします。",
        epilog=(
            "システム依存: ffmpeg が PATH に存在する必要があります。\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  macOS:         brew install ffmpeg"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files",
        nargs="+",
        metavar="AUDIO_FILE",
        help="文字起こしする音声ファイル（複数指定可）",
    )
    parser.add_argument(
        "--model", "-m",
        default="small",
        choices=SUPPORTED_MODELS,
        help="Whisper モデルサイズ（デフォルト: small）",
    )
    parser.add_argument(
        "--language", "-l",
        default="ja",
        help="言語ヒント（デフォルト: ja）。英語なら 'en' など",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        metavar="PATH",
        help="出力先ファイルパス（複数ファイル時はディレクトリパスとして扱う）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Whisper の内部進捗ログを表示する",
    )
    return parser.parse_args()


def resolve_output_path(output_arg, input_path, multi_file):
    """output 引数からファイルの書き出し先パスを決定する。"""
    if output_arg is None:
        return None
    if multi_file:
        stem = os.path.splitext(os.path.basename(input_path))[0]
        return os.path.join(output_arg, f"{stem}.txt")
    return output_arg


def main():
    args = parse_args()

    # 入力ファイルの存在確認（モデルロード前に全チェック）
    missing = [f for f in args.files if not os.path.isfile(f)]
    if missing:
        for path in missing:
            print(f"[error] ファイルが見つかりません: {path}", file=sys.stderr)
        sys.exit(1)

    # openai-whisper のインポート
    try:
        import whisper
    except ImportError:
        print(
            "[error] openai-whisper がインストールされていません。\n"
            "       pip install openai-whisper を実行してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    # モデルロード（初回はキャッシュにダウンロードされます）
    print(f"[info] モデルをロード中: {args.model}", file=sys.stderr)
    try:
        model = whisper.load_model(args.model)
    except Exception as exc:
        print(f"[error] モデルのロードに失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    multi_file = len(args.files) > 1

    for i, audio_path in enumerate(args.files):
        if multi_file:
            print(f"\n[info] 処理中 ({i + 1}/{len(args.files)}): {audio_path}", file=sys.stderr)

        try:
            result = model.transcribe(
                audio_path,
                language=args.language,
                verbose=True if args.verbose else None,
            )
        except Exception as exc:
            print(f"[error] 文字起こし失敗: {audio_path} → {exc}", file=sys.stderr)
            continue

        text = result["text"].strip()

        # stdout へ出力
        if multi_file:
            print(f"=== {os.path.basename(audio_path)} ===")
        print(text)

        # ファイル保存
        out_path = resolve_output_path(args.output, audio_path, multi_file)
        if out_path:
            if multi_file:
                os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            print(f"[saved] {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
