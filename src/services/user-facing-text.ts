const INTERNAL_LINE_REFERENCE = /(?:[（(\[]\s*)?\bL\d{2,4}(?:\s*[-–—~至]\s*L?\d{2,4})?\b(?:\s*[）)\]])?\s*[：:]?\s*/gi;

export function cleanUserFacingText(value: string) {
  return value
    .replace(INTERNAL_LINE_REFERENCE, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}
