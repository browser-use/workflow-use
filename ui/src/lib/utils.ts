import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getUniqueWorkflowName(
  baseName: string,
  existingNames: string[]
): string {
  const name = baseName.trim();
  let newName = name;
  let counter = 2;

  const nameSet = new Set(existingNames.map((n) => n.trim()));

  while (nameSet.has(newName)) {
    newName = `${name} (${counter})`;
    counter++;
  }

  return newName;
}
