import os
import xml.etree.ElementTree as ET
import asyncio
import aiohttp

# Define paths
source_folder = './'
target_folder = './locales/ua'

# Ensure target folder exists
os.makedirs(target_folder, exist_ok=True)

# Semaphore to limit concurrent requests
semaphore = asyncio.Semaphore(50)

async def translate_text(session, text, src='en', dest='uk'):
    """Translate text using an async API call."""
    async with semaphore:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": src,
            "tl": dest,
            "dt": "t",
            "q": text
        }
        async with session.get(url, params=params) as response:
            result = await response.json()
            return result[0][0][0] if result else text

async def process_file(file_name, session):
    """Process a single file asynchronously."""
    source_file_path = os.path.join(source_folder, file_name)
    target_file_path = os.path.join(target_folder, file_name)

#     if os.path.exists(target_file_path) or file_name == 'NAC.qt.ts':
#         print(f'Skipping {file_name}, already exists in target folder.')
#         return

    print(f'Translating {file_name}...')
    tree = ET.parse(source_file_path)
    root = tree.getroot()

    # Translate content in <source> tags and update <translation> tags
    for message_tag in root.findall(".//message"):
        source_tag = message_tag.find("source")
        translation_tag = message_tag.find("translation")
        if source_tag is not None and source_tag.text:
            translated_text = await translate_text(session, source_tag.text)
            if translation_tag is not None and 'type' in translation_tag.attrib and translation_tag.attrib['type'] == 'unfinished':
                print(f"\rTranslating message: {source_tag.text}", end='\r')
                translation_tag.text = translated_text
                del translation_tag.attrib['type']
                # Save intermediate results
                tree.write(target_file_path, encoding='utf-8', xml_declaration=True)

    # Save updated XML to target folder
    tree.write(target_file_path, encoding='utf-8', xml_declaration=True)
    print(f'Translated {file_name} and saved to {target_file_path}')

async def main():
    """Main function to process all files asynchronously."""
    async with aiohttp.ClientSession() as session:
        tasks = [
            process_file(file_name, session)
            for file_name in os.listdir(source_folder)
            if file_name.endswith('.qt.ts')
        ]
        await asyncio.gather(*tasks)

# Run the async main function
asyncio.run(main())
