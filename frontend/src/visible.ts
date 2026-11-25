/** Make invisible characters visible, so " the" and "the" do not look the same. */
export function visible(s: string): string {
  return s
    .replace(/ /g, "·")
    .replace(/\n/g, "↵")
    .replace(/\t/g, "→")
    .replace(/\r/g, "␍");
}

/** Same as visible(), but each newline also stays a real line break, so a chip that
 *  contains "\n" still breaks the line in the coloured text. */
export function visibleInline(s: string): string {
  return visible(s).replace(/↵/g, "↵\n");
}
