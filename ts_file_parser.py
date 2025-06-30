import json
import xml.etree.ElementTree as elementTree
from pathlib import Path
import re

def clean_text(text):
    return re.sub(r'\s+', ' ', text.strip())

def extract_messages_from_zone(zone_data):
    messages = []

    if "name" in zone_data:
        messages.append(clean_text(zone_data["name"]))

    if "params" in zone_data and isinstance(zone_data["params"], list):
        for param in zone_data["params"]:
            if isinstance(param, dict):
                if "name" in param:
                    messages.append(clean_text(param["name"]))
                if "params" in param:
                    for subparam in param["params"]:
                        if "name" in subparam:
                            messages.append(clean_text(subparam["name"]))

    for key, value in zone_data.items():
        if isinstance(value, dict):
            if "name" in value:
                messages.append(clean_text(value["name"]))
            if "params" in value:
                for param in value["params"]:
                    if "name" in param:
                        messages.append(clean_text(param["name"]))

    return messages

def find_name_line_numbers(json_text):
    name_lines = {}
    pattern = re.compile(r'"name"\s*:\s*("(?:[^"\\]|\\.)*")')
    for i, line in enumerate(json_text.splitlines(), start=1):
        match = pattern.search(line)
        if match:
            raw_value = match.group(1)
            try:
                unescaped_value = json.loads(raw_value)
                clean_value = clean_text(unescaped_value)
                if clean_value not in name_lines:
                    name_lines[clean_value] = i
            except json.JSONDecodeError:
                pass
    return name_lines

def convert_json_to_ts(json_path: Path, output_dir: Path):
    with open(json_path, 'r', encoding='utf-8') as f:
        json_text = f.read()
    data = json.loads(json_text)

    name_line_map = find_name_line_numbers(json_text)

    device_name = data.get("name", json_path.stem)
    output_filename = f"{device_name}.qt.ts"
    output_path = output_dir / output_filename

    relative_location = f"../{json_path.as_posix()}"

    ts = elementTree.Element('TS', version="2.1", sourcelanguage="en")
    context = elementTree.SubElement(ts, 'context')
    name = elementTree.SubElement(context, 'name')
    name.text = "MainWindow"

    zones = data.get("zones", {})
    unique_sources = set()

    for zone_id, zone in zones.items():
        messages = extract_messages_from_zone(zone)
        context.append(elementTree.Comment(f"Json file: {device_name}, Zone: {zone_id}"))

        for msg in messages:
            if msg in unique_sources:
                continue
            unique_sources.add(msg)

            message = elementTree.SubElement(context, 'message')
            location = elementTree.SubElement(message, 'location')
            location.set('filename', relative_location)

            line_num = name_line_map.get(msg)
            if line_num is not None:
                location.set('line', str(line_num))

            source = elementTree.SubElement(message, 'source')
            source.text = msg

            translation = elementTree.SubElement(message, 'translation')
            translation.set('type', 'unfinished')

    elementTree.indent(ts, space="    ", level=0)
    tree = elementTree.ElementTree(ts)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)

    print(f"[✓] Generated: {output_path}")

def process_all_jsons(json_root: str, output_dir: str):
    json_root_path = Path(json_root)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for json_file in json_root_path.rglob("*.json"):
        print(f"[i] Processing {json_file}")
        convert_json_to_ts(json_file, output_path)

if __name__ == "__main__":
    process_all_jsons("./json", "./localization")
