'use client';

import { useState, useEffect, ChangeEvent, FormEvent, Fragment, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import api from '@/lib/api';
import { UserCircleIcon, PencilIcon, ArrowLeftIcon, CheckCircleIcon, ArrowUpOnSquareIcon } from '@heroicons/react/24/solid';
import { FaUser } from 'react-icons/fa';
import { Transition } from '@headlessui/react';

interface UserProfile {
  email: string;
  username: string | null;
  full_name: string | null;
  profile_image_url: string | null;
}

const ProfilePage = () => {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [formData, setFormData] = useState({ username: '', full_name: '' });
  
  const [isEditingUsername, setIsEditingUsername] = useState(false);
  const [isEditingFullName, setIsEditingFullName] = useState(false);
  
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [newProfileImageFile, setNewProfileImageFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get<UserProfile>('/users/me');
        setProfile(response.data);
        setFormData({
          username: response.data.username || '',
          full_name: response.data.full_name || '',
        });
      } catch (err: any) {
        if (err.response?.status === 401) {
          router.push('/login');
        } else {
          setError('Failed to load profile. Please try again later.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchProfile();

    // Cleanup for the image preview URL
    return () => {
      if (imagePreviewUrl) {
        URL.revokeObjectURL(imagePreviewUrl);
      }
    };
  }, [router, imagePreviewUrl]);
  
  const hasTextFieldChanges =
    profile &&
    (formData.full_name !== (profile.full_name || '') ||
      formData.username !== (profile.username || ''));
      
  const hasChanges = hasTextFieldChanges || !!newProfileImageFile;

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handlePfpButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setNewProfileImageFile(file);
      if (imagePreviewUrl) {
        URL.revokeObjectURL(imagePreviewUrl);
      }
      setImagePreviewUrl(URL.createObjectURL(file));
    }
  };
  
  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    if (!hasChanges) return;

    setIsSaving(true);
    setError('');
    setSuccessMessage('');

    let updatedProfile = profile;

    try {
      // 1. Upload new profile image if one has been selected
      if (newProfileImageFile) {
        const imageFormData = new FormData();
        imageFormData.append('profile_image', newProfileImageFile);

        const imageResponse = await api.put<UserProfile>('/users/me/profile-image', imageFormData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        updatedProfile = imageResponse.data;
        setProfile(updatedProfile); // Update profile state immediately
        setNewProfileImageFile(null);
        if (imagePreviewUrl) {
            URL.revokeObjectURL(imagePreviewUrl);
        }
        setImagePreviewUrl(null);
      }

      // 2. Update text fields if they have changed
      if (hasTextFieldChanges) {
          const textResponse = await api.put<UserProfile>('/users/me', {
            username: formData.username,
            full_name: formData.full_name,
          });
          updatedProfile = textResponse.data;
          setProfile(updatedProfile); // Update profile state with final data
          setIsEditingFullName(false);
          setIsEditingUsername(false);
      }
      
      setFormData({
        username: updatedProfile?.username || '',
        full_name: updatedProfile?.full_name || '',
      });

      setSuccessMessage('Profile updated successfully!');
      setTimeout(() => setSuccessMessage(''), 3000);

    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update profile.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="text-center p-10">Loading profile...</div>;
  }

  if (error && !profile) {
    return <div className="text-center p-10 text-red-500">{error}</div>;
  }

  if (!profile) {
    return <div className="text-center p-10">Could not load profile.</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-6 lg:p-8">
        <div className="max-w-2xl mx-auto">
            <div className="mb-6">
                <Link href="/" className="inline-flex items-center text-sm font-medium text-gray-600 hover:text-blue-600">
                    <ArrowLeftIcon className="h-4 w-4 mr-2" />
                    Back to Dashboard
                </Link>
            </div>
            
            <form onSubmit={handleSave} className="bg-white p-8 rounded-xl shadow-md">
                <div className="flex flex-col items-center mb-8">
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        className="hidden"
                        accept="image/png, image/jpeg, image/gif"
                    />
                    <button
                        type="button"
                        onClick={handlePfpButtonClick}
                        disabled={isSaving}
                        className="relative rounded-full group"
                    >
                        {imagePreviewUrl ? (
                            <img
                            src={imagePreviewUrl}
                            alt="Profile Preview"
                            className="w-32 h-32 rounded-full object-cover border-4 border-gray-200 group-hover:opacity-70 transition-opacity"
                            />
                        ) : profile?.profile_image_url ? (
                            <img
                            src={profile.profile_image_url}
                            alt="Profile"
                            className="w-32 h-32 rounded-full object-cover border-4 border-gray-200 group-hover:opacity-70 transition-opacity"
                            />
                        ) : (
                            <img
                                src={`https://ui-avatars.com/api/?name=${encodeURIComponent(profile.username || profile.full_name || 'User')}&background=random&color=fff&size=128&length=2`}
                                alt="Default Profile"
                                className="w-32 h-32 rounded-full object-cover border-4 border-gray-200 group-hover:opacity-70 transition-opacity"
                            />
                        )}
                        <div className="absolute inset-0 bg-transparent group-hover:bg-black group-hover:bg-opacity-50 flex flex-col items-center justify-center rounded-full transition-all duration-300">
                            <ArrowUpOnSquareIcon className={`h-8 w-8 text-white opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${isSaving ? 'animate-pulse' : ''}`} />
                            <span className="text-white text-xs mt-1 opacity-0 group-hover:opacity-100 transition-opacity">{isSaving ? 'Saving...' : 'Change'}</span>
                        </div>
                    </button>
                </div>
            
                <div className="space-y-6">
                    {/* Full Name */}
                    <div>
                        <label className="text-sm font-bold text-gray-600 mb-1 block">Full Name</label>
                        <div className="flex items-center">
                            <input
                                type="text"
                                name="full_name"
                                value={formData.full_name}
                                onChange={handleInputChange}
                                readOnly={!isEditingFullName}
                                className={`w-full p-3 border rounded-lg transition-all duration-200 ${
                                isEditingFullName
                                    ? 'bg-white border-blue-400 ring-2 ring-blue-200 text-gray-900'
                                    : 'bg-gray-100 border-gray-200 text-gray-700'
                                }`}
                            />
                            <button type="button" onClick={() => setIsEditingFullName(!isEditingFullName)} className="p-2 ml-2 text-gray-500 hover:text-blue-600">
                                <PencilIcon className="h-5 w-5"/>
                            </button>
                        </div>
                    </div>

                    {/* Username */}
                    <div>
                        <label className="text-sm font-bold text-gray-600 mb-1 block">Username</label>
                        <div className="flex items-center">
                            <input
                                type="text"
                                name="username"
                                value={formData.username}
                                onChange={handleInputChange}
                                readOnly={!isEditingUsername}
                                className={`w-full p-3 border rounded-lg transition-all duration-200 ${
                                isEditingUsername
                                    ? 'bg-white border-blue-400 ring-2 ring-blue-200 text-gray-900'
                                    : 'bg-gray-100 border-gray-200 text-gray-700'
                                }`}
                            />
                            <button type="button" onClick={() => setIsEditingUsername(!isEditingUsername)} className="p-2 ml-2 text-gray-500 hover:text-blue-600">
                                <PencilIcon className="h-5 w-5"/>
                            </button>
                        </div>
                    </div>

                    {/* Email (Read-only) */}
                    <div>
                        <label className="text-sm font-bold text-gray-600 mb-1 block">Email</label>
                        <input
                            type="email"
                            value={profile.email}
                            readOnly
                            className="w-full p-3 border rounded-lg bg-gray-100 border-gray-200 text-gray-500 cursor-not-allowed"
                        />
                    </div>
                </div>

                <div className="mt-8">
                     {/* Save Button */}
                    <button
                        type="submit"
                        disabled={!hasChanges || isSaving}
                        className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isSaving ? 'Saving...' : 'Save Changes'}
                    </button>
                    
                    {/* Success Message */}
                    <Transition
                        show={!!successMessage}
                        as={Fragment}
                        enter="transition ease-out duration-200"
                        enterFrom="opacity-0 translate-y-1"
                        enterTo="opacity-100 translate-y-0"
                        leave="transition ease-in duration-150"
                        leaveFrom="opacity-100 translate-y-0"
                        leaveTo="opacity-0 translate-y-1"
                    >
                        <div className="mt-4 flex items-center justify-center text-sm text-green-600">
                            <CheckCircleIcon className="h-5 w-5 mr-2" />
                            {successMessage}
                        </div>
                    </Transition>
                    
                    {/* Error Message */}
                    {error && (
                        <p className="mt-4 text-center text-sm text-red-600">{error}</p>
                    )}
                </div>
            </form>
        </div>
    </div>
  );
};

export default ProfilePage; 