#!/usr/bin/env python3
#
# Generate Subtitles (.ass) with Sensitivity Masking
#
# Usage: python generate_subtitles.py <transcription.json> <sensitivity.json> -o <subtitles.ass>
#

import argparse
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def format_time_ass(seconds: float) -> str:
    """Convert seconds to ASS time format (H:MM:SS.cc)"""
    total_ms = int(round(seconds * 100)) # ASS uses centiseconds
    hours = total_ms // 360000
    minutes = (total_ms % 360000) // 6000
    secs = (total_ms % 6000) // 100
    cs = total_ms % 100
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"

def is_sensitive(start_ms: int, end_ms: int, sensitivity_list: list) -> bool:
    """Check if a time interval overlaps with any sensitive interval."""
    # Simple overlap check
    for item in sensitivity_list:
        s_start = item["start_time"]
        s_end = item["end_time"]
        # Check for overlap: not (end1 < start2 or start1 > end2)
        if not (end_ms <= s_start or start_ms >= s_end):
            return True
    return False

def generate_ass(transcription: dict, sensitivity: list, output_path: str):
    events = []
    
    for segment in transcription.get("segments", []):
        start_time = segment["start"]
        end_time = segment["end"]
        
        # Reconstruct text from words to handle masking precisely
        words = segment.get("words", [])
        display_text_parts = []
        
        if words:
            for word_info in words:
                word_text = word_info["word"]
                w_start_ms = int(word_info["start"] * 1000)
                w_end_ms = int(word_info["end"] * 1000)
                
                if is_sensitive(w_start_ms, w_end_ms, sensitivity):
                    # Mask the word
                    display_text_parts.append("*" * len(word_text))
                else:
                    display_text_parts.append(word_text)
            
            # Join words (naive join, assuming spaces for English, no spaces for Chinese? 
            # Whisper usually includes leading spaces in 'word' for Latin languages)
            # But let's just join empty and rely on the spaces captured in `word` if any, 
            # or add space if needed. faster-whisper words usually have spaces attached.
            # Actually faster-whisper structure: ' word'.
            
            final_text = "".join(display_text_parts)
            
        else:
            # Fallback if no word timestamps (shouldn't happen with our config)
            final_text = segment["text"]
        
        events.append({
            "start": format_time_ass(start_time),
            "end": format_time_ass(end_time),
            "text": final_text
        })
        
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ASS_HEADER)
        for e in events:
            # Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,Text
            line = f"Dialogue: 0,{e['start']},{e['end']},Default,,0,0,0,,{e['text']}\n"
            f.write(line)

def main():
    parser = argparse.ArgumentParser(description="Generate ASS Subtitles with Masking")
    parser.add_argument("transcription_file", help="Path to transcription.json")
    parser.add_argument("sensitivity_file", help="Path to sensitivity.json")
    parser.add_argument("-o", "--output", default="subtitles.ass", help="Output ASS path")
    
    args = parser.parse_args()
    
    with open(args.transcription_file, "r", encoding="utf-8") as f:
        transcription = json.load(f)
        
    sensitivity = []
    if Path(args.sensitivity_file).exists():
        with open(args.sensitivity_file, "r", encoding="utf-8") as f:
            sensitivity = json.load(f)
    else:
        logger.warning(f"Sensitivity file {args.sensitivity_file} not found. Proceeding without masking.")

    generate_ass(transcription, sensitivity, args.output)
    logger.info(f"Generated subtitles at {args.output}")

if __name__ == "__main__":
    main()
