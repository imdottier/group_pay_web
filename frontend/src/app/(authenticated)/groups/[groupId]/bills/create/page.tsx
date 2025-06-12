'use client';

import { useParams } from 'next/navigation';
import CreateBillForm from '@/components/bills/CreateBillForm';
import Link from 'next/link';

export default function CreateBillPage() {
  const params = useParams();
  const groupId = Array.isArray(params.groupId) ? params.groupId[0] : params.groupId;

  if (!groupId) {
    return <div className="text-center py-10">Group not found.</div>;
  }

  return (
    <div className="container mx-auto p-4 md:p-8">
        <div className="mb-6">
            <Link href={`/groups/${groupId}`} passHref>
                <span className="text-indigo-600 hover:text-indigo-800 transition-colors duration-150 ease-in-out cursor-pointer">
                    &larr; Back to Group
                </span>
            </Link>
        </div>
        <div className="max-w-2xl mx-auto bg-white p-8 rounded-lg shadow-md">
            <CreateBillForm groupId={groupId} />
        </div>
    </div>
  );
} 