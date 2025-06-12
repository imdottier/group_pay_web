import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Rounds a number to the nearest 500.
 * @param amount The number to round.
 * @returns The rounded number.
 */
export function roundToNearest500(amount: number): number {
  return Math.round(amount / 500) * 500;
}

/**
 * Formats a number as a currency string (VND), with rounding and separators.
 * @param amount The number to format.
 * @param options Options for formatting.
 * @param options.rounding Round to the nearest 500. Defaults to true.
 * @param options.notation Compact or standard notation. Defaults to 'standard'.
 * @returns The formatted currency string.
 */
export function formatCurrency(
  amount: number | undefined | null,
  options: { rounding?: boolean, notation?: 'compact' | 'standard' } = {}
): string {
  const { rounding = true, notation = 'standard' } = options;
  if (amount === null || amount === undefined) {
    return "0 ₫";
  }

  const numberAmount = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(numberAmount)) {
    return "0 ₫";
  }

  const amountToFormat = rounding ? roundToNearest500(numberAmount) : numberAmount;

  const formattedAmount = new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    notation: notation,
  }).format(amountToFormat);

  return formattedAmount;
}

/**
 * Gets the user's role in a group.
 * @param user The user object.
 * @param groupId The ID of the group.
 * @returns The user's role in the group ('owner', 'admin', or 'member').
 */
export function get_user_role(user: any, groupId: number): string {
  if (!user?.groups) return 'member';
  const group = user.groups.find((g: any) => g.group_id === groupId);
  return group?.role || 'member';
}