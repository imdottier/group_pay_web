export interface User {
    user_id: number;
    username: string;
    email?: string;
    full_name: string | null;
    profile_image_url?: string;
}

export enum FriendshipStatus {
    pending = 'pending',
    accepted = 'accepted',
    declined = 'declined',
    blocked = 'blocked',
}

export interface Friendship {
    requester_id: number;
    addressee_id: number;
    status: FriendshipStatus;
    created_at: string;
    requester: User;
    addressee: User;
}

export type GroupRole = 'owner' | 'admin' | 'member';

export interface GroupMember {
    user: User;
    role: GroupRole;
}

export interface Group {
    group_id: number;
    group_name: string;
    description: string | null;
    members: GroupMember[];
}

export interface InitialPayer {
  user_id: number;
  amount_paid: number;
}

export interface BillPart {
  user: User;
  amount_owed: string;
}

export interface BillItemSplit {
  user: User;
  quantity: number;
}

export interface BillItem {
  item_id: number;
  name: string;
  unit_price: number;
  quantity: number;
  bill_item_splits: BillItemSplit[];
}

export interface InitialPayment {
  user: User;
  amount_paid: string;
}

export interface Bill {
  bill_id: number;
  title: string;
  description?: string;
  total_amount: number;
  created_by: number;
  bill_creator: User;
  created_at: string;
  split_method: 'equal' | 'exact' | 'item';
  initial_payments: InitialPayment[];
  bill_parts: BillPart[];
  items: BillItem[];
} 