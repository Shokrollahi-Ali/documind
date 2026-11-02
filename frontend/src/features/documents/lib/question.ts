export const maxQuestionLength = 2000;

const numberFormat = new Intl.NumberFormat("en");

export function countQuestionCharacters(question: string): number {
  return Array.from(question).length;
}

export function formatQuestionCounter(question: string): string {
  const count = numberFormat.format(countQuestionCharacters(question));
  const maximum = numberFormat.format(maxQuestionLength);

  return `${count} / ${maximum}`;
}

export function validateQuestion(question: string): string | null {
  const trimmedQuestion = question.trim();

  if (!trimmedQuestion) return "Enter a question first.";

  if (countQuestionCharacters(trimmedQuestion) > maxQuestionLength) {
    return `Questions can be at most ${numberFormat.format(maxQuestionLength)} characters.`;
  }

  return null;
}
