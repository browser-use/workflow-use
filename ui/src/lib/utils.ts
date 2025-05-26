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

  const nameRegex = new RegExp(`^${name}(?: \\((\\d+)\\))*$`);

  let maxNumber = 1;
  for (const existingName of existingNames) {
    const match = existingName.trim().match(nameRegex);
    if (match) {
      // If there's a number in parentheses, get it
      const number = match[1] ? parseInt(match[1], 10) : 1;
      maxNumber = Math.max(maxNumber, number + 1);
    }
  }

  if (existingNames.includes(name)) {
    newName = `${name} (${maxNumber})`;
  } else {
    newName = name;
  }

  return newName;
}
