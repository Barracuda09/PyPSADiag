import os
import xml.etree.ElementTree as ET
from googletrans import Translator

# Define paths
source_folder = './'
target_folder = './locales/ua'

# Initialize translator
translator = Translator()

# Ensure target folder exists
os.makedirs(target_folder, exist_ok=True)

# Translate specific XML tags
for file_name in os.listdir(source_folder):
    if file_name.endswith('.qt.ts'):
        source_file_path = os.path.join(source_folder, file_name)
        target_file_path = os.path.join(target_folder, file_name)

        if os.path.exists(target_file_path) or file_name == 'NAC.qt.ts':
            print(f'Skipping {file_name}, already exists in target folder.')
            continue
        print(f'Translating {file_name}...')
        # Parse XML file
        tree = ET.parse(source_file_path)
        root = tree.getroot()

        # Translate content in <source> tags and update <translation> tags
        for message_tag in root.findall(".//message"):
            source_tag = message_tag.find("source")
            translation_tag = message_tag.find("translation")
            if source_tag is not None and source_tag.text:
                translated_text = translator.translate(source_tag.text, src='en', dest='uk').text
                if translation_tag is not None:
                    translation_tag.text = translated_text
                    if 'type' in translation_tag.attrib and translation_tag.attrib['type'] == 'unfinished':
                        del translation_tag.attrib['type']

        # Save updated XML to target folder
        tree.write(target_file_path, encoding='utf-8', xml_declaration=True)
        print(f'Translated {file_name} and saved to {target_file_path}')
