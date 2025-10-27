#!/usr/bin/env python3
"""
Migration script to convert existing JSON workflow files to YAML format.

Usage:
    python migrate_json_to_yaml.py [--directory path/to/workflows] [--dry-run]
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml


def migrate_workflow(json_path: Path, backup: bool = True) -> bool:
	"""
	Convert a single JSON workflow file to YAML.

	Args:
	    json_path: Path to the JSON workflow file
	    backup: Whether to create a .bak backup of the original

	Returns:
	    True if successful, False otherwise
	"""
	try:
		# Read JSON
		with open(json_path, 'r') as f:
			data = json.load(f)

		# Create YAML path
		yaml_path = json_path.with_suffix('.yaml')

		# Backup original if requested
		if backup:
			backup_path = json_path.with_suffix(json_path.suffix + '.bak')
			shutil.copy2(json_path, backup_path)
			print(f'  ✓ Backed up to: {backup_path.name}')

		# Write YAML
		with open(yaml_path, 'w') as f:
			yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

		print(f'  ✓ Created YAML: {yaml_path.name}')

		# Remove original JSON (only if backup was created)
		if backup:
			json_path.unlink()
			print(f'  ✓ Removed JSON: {json_path.name}')

		return True

	except Exception as e:
		print(f'  ✗ Error migrating {json_path.name}: {e}')
		return False


def update_metadata(metadata_path: Path, dry_run: bool = False) -> bool:
	"""
	Update metadata.json to point to .yaml files instead of .json files.

	Args:
	    metadata_path: Path to metadata.json
	    dry_run: If True, only print what would be changed

	Returns:
	    True if successful, False otherwise
	"""
	try:
		if not metadata_path.exists():
			print(f'No metadata file found at {metadata_path}')
			return True

		with open(metadata_path, 'r') as f:
			metadata = json.load(f)

		updated_count = 0
		for workflow_id, workflow_meta in metadata.items():
			if 'file_path' in workflow_meta:
				old_path = workflow_meta['file_path']
				if old_path.endswith('.json'):
					# Only replace the final .json extension, not all occurrences in the path
					new_path = old_path[:-5] + '.yaml'  # Remove '.json' (5 chars) and add '.yaml'
					if dry_run:
						print(f'  Would update: {old_path} → {new_path}')
					else:
						workflow_meta['file_path'] = new_path
					updated_count += 1

		if not dry_run and updated_count > 0:
			# Backup metadata
			backup_path = metadata_path.with_suffix('.json.bak')
			shutil.copy2(metadata_path, backup_path)

			# Write updated metadata
			with open(metadata_path, 'w') as f:
				json.dump(metadata, f, indent=2)

			print(f'✓ Updated {updated_count} file paths in metadata.json')
			print('✓ Backed up original to metadata.json.bak')
		elif dry_run and updated_count > 0:
			print(f'Would update {updated_count} file paths in metadata.json')

		return True

	except Exception as e:
		print(f'✗ Error updating metadata: {e}')
		return False


def migrate_directory(directory: Path, pattern: str = '*.workflow.json', dry_run: bool = False, backup: bool = True):
	"""
	Migrate all workflow JSON files in a directory to YAML.

	Args:
	    directory: Directory to scan
	    pattern: Glob pattern to match workflow files
	    dry_run: If True, only print what would be done
	    backup: Whether to create backups
	"""
	workflow_files = list(directory.rglob(pattern))

	if not workflow_files:
		print(f"No workflow files matching '{pattern}' found in {directory}")
		return

	print(f'\nFound {len(workflow_files)} workflow file(s) to migrate:\n')

	success_count = 0
	fail_count = 0

	for json_path in workflow_files:
		print(f'Migrating: {json_path.relative_to(directory)}')

		if dry_run:
			print(f'  [DRY RUN] Would convert to: {json_path.with_suffix(".yaml").name}')
			success_count += 1
		else:
			if migrate_workflow(json_path, backup=backup):
				success_count += 1
			else:
				fail_count += 1
		print()

	# Update metadata files
	print('\nUpdating metadata files...')
	for metadata_path in directory.rglob('metadata.json'):
		print(f'\nProcessing metadata: {metadata_path.relative_to(directory)}')
		update_metadata(metadata_path, dry_run=dry_run)

	# Summary
	print('\n' + '=' * 60)
	if dry_run:
		print('DRY RUN SUMMARY:')
		print(f'  Would migrate: {success_count} files')
	else:
		print('MIGRATION SUMMARY:')
		print(f'  ✓ Successfully migrated: {success_count} files')
		if fail_count > 0:
			print(f'  ✗ Failed: {fail_count} files')
	print('=' * 60)


def main():
	parser = argparse.ArgumentParser(
		description='Migrate JSON workflow files to YAML format',
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog="""
Examples:
  # Dry run - see what would be migrated
  python migrate_json_to_yaml.py --dry-run

  # Migrate workflows in current directory
  python migrate_json_to_yaml.py

  # Migrate workflows in specific directory
  python migrate_json_to_yaml.py --directory /path/to/workflows

  # Migrate without creating backups (not recommended)
  python migrate_json_to_yaml.py --no-backup
        """,
	)

	parser.add_argument(
		'--directory',
		'-d',
		type=Path,
		default=Path('.'),
		help='Directory to search for workflow files (default: current directory)',
	)

	parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without making changes')

	parser.add_argument('--no-backup', action='store_true', help='Do not create .bak backup files (not recommended)')

	parser.add_argument(
		'--pattern', default='*.workflow.json', help='Glob pattern to match workflow files (default: *.workflow.json)'
	)

	args = parser.parse_args()

	directory = args.directory.resolve()

	if not directory.exists():
		print(f'Error: Directory does not exist: {directory}')
		sys.exit(1)

	if not directory.is_dir():
		print(f'Error: Not a directory: {directory}')
		sys.exit(1)

	print('=' * 60)
	print('JSON to YAML Workflow Migration')
	print('=' * 60)
	print(f'Directory: {directory}')
	print(f'Pattern: {args.pattern}')
	print(f'Dry run: {args.dry_run}')
	print(f'Create backups: {not args.no_backup}')

	migrate_directory(directory=directory, pattern=args.pattern, dry_run=args.dry_run, backup=not args.no_backup)


if __name__ == '__main__':
	main()
