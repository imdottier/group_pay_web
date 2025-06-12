export interface User {
    user_id: number;
    username: string;
    email: string;
    full_name: string | null;
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