#!/usr/bin/env python3
"""
Semantic Extraction Demo Script

This script demonstrates how the semantic extractor analyzes web pages
and creates text-to-selector mappings for automation.

Usage:
    python semantic_extraction_demo.py [--url URL] [--html-file PATH] [--demo]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict

import aiofiles

# Add the workflow_use package to the path
sys.path.append(str(Path(__file__).parent.parent))

from browser_use import Browser

from workflow_use.workflow.semantic_extractor import SemanticExtractor


class SemanticExtractionDemo:
	"""Demo class for semantic extraction."""

	def __init__(self):
		self.extractor = SemanticExtractor()
		self.browser = None

	async def __aenter__(self):
		"""Async context manager entry."""
		self.browser = Browser()
		return self

	async def __aexit__(self, exc_type, exc_val, exc_tb):
		"""Async context manager exit."""
		if self.browser:
			await self.browser.close()

	async def demo_from_url(self, url: str):
		"""Demonstrate extraction from a real URL."""
		print(f'\n🔍 DEMO: Real Page Extraction from {url}')
		print('=' * 50)

		try:
			page = await self.browser.get_current_page()
			await page.goto(url, wait_until='domcontentloaded')

			mapping = await self.extractor.extract_semantic_mapping(page)

			print(f'📊 Extracted {len(mapping)} interactive elements from real page:')
			print()

			# Show first 10 elements as example
			count = 0
			for text, info in mapping.items():
				if count >= 10:
					print(f'   ... and {len(mapping) - 10} more elements')
					break

				element_type = info.get('element_type', 'unknown')
				selector = info.get('selectors', '')
				print(f"   • [{element_type}] '{text[:50]}{'...' if len(text) > 50 else ''}' → {selector}")
				count += 1

			return mapping

		except Exception as e:
			print(f'❌ Error loading page: {e}')
			return {}

	async def save_mapping_to_file(self, mapping: Dict[str, Any], filename: str):
		"""Save the mapping to a JSON file for inspection."""
		filepath = Path(filename)

		# Make mapping JSON serializable
		clean_mapping = {}
		for text, info in mapping.items():
			clean_mapping[text] = {
				'class': info.get('class', ''),
				'id': info.get('id', ''),
				'selectors': info.get('selectors', ''),
				'fallback_selector': info.get('fallback_selector', ''),
				'text_xpath': info.get('text_xpath', ''),
				'element_type': info.get('element_type', ''),
				'deterministic_id': info.get('deterministic_id', ''),
			}

		async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
			await f.write(json.dumps(clean_mapping, indent=2, ensure_ascii=False))

		print(f'💾 Saved semantic mapping to: {filepath}')


async def main():
	"""Main demo function."""
	parser = argparse.ArgumentParser(description='Semantic Extraction Demo')
	parser.add_argument('--url', help='Extract from a specific URL')
	parser.add_argument('--html-file', help='Extract from an HTML file')
	parser.add_argument('--save', help='Save mapping to JSON file')
	args = parser.parse_args()

	async with SemanticExtractionDemo() as demo:
		print('🚀 Semantic Abstraction Demo')
		print('=' * 60)
		print('This demo shows how visible text maps to deterministic selectors')
		print('for reliable web automation without AI/LLM dependencies.')
		print()

		mapping = {}

		if args.url:
			mapping = await demo.demo_from_url(args.url)
		elif args.html_file:
			html_path = Path(args.html_file)
			if html_path.exists():
				html_content = html_path.read_text(encoding='utf-8')
				page = await demo.browser.get_current_page()
				await page.set_content(html_content)
				mapping = await demo.extractor.extract_semantic_mapping(page)
				print(f'📊 Extracted {len(mapping)} elements from {html_path}')
			else:
				print(f'❌ HTML file not found: {html_path}')
		else:
			# Default: run government form demo
			mapping = await demo.demo_complex_form()

		if args.save and mapping:
			await demo.save_mapping_to_file(mapping, args.save)

		print('\n🎉 Demo completed!')


if __name__ == '__main__':
	asyncio.run(main())
