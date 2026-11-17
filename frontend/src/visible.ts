/** Make invisible characters visible, so " the" and "the" do not look the same. */
export function visible(s: string): string {
  return s
    .replace(/ /g, "·")
    .replace(/\n/g, "↵")
    .replace(/\t/g, "→")
    .replace(/\r/g, "␍");
}
