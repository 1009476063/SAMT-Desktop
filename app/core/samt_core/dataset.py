import torch
import pickle
from Nii_utils import NiiDataRead, NiiDataRead_2D
import numpy as np
import pandas as pd
from monai.transforms import Compose, Rand2DElasticd, Rand3DElasticd, RandRotated, RandGaussianNoised, Rand3DElastic, RandFlipd, ToTensor
import os
from torch.utils.data import Dataset, DataLoader
from skimage import transform
from utils import masked_Zscore_norm
import glob
from monai.utils import set_determinism
from scipy.ndimage import distance_transform_edt

set_determinism(seed=9)


mean_std_dict = {'Age': [48.68514851, 10.91070313],
                 'Tumor size MRI ': [2.644158416, 1.542471507],
                 'SLN-positive': [1.57746478873239, 0.916236742769841], 'total SLN': [3.98591549295775, 2.14888929897284],
                 'Positive_Total_SLN_ratio': [0.5, 0.25]}

def Extract_clinical_features(metadata_df, ID):
    Clinical_features = []
    affected_side = str(metadata_df.loc[metadata_df['ID'] == ID, 'Laterality '].values[0])
    if 'Left' in affected_side and 'Right' not in affected_side:
        Clinical_features.append(torch.tensor([1, 0]))
    elif 'Right' in affected_side and 'Left' not in affected_side:
        Clinical_features.append(torch.tensor([0, 1]))
    else:
        Clinical_features.append(torch.tensor([0, 0]))

    num_tumor = str(metadata_df.loc[metadata_df['ID'] == ID, 'Multifocality（Tumor number）'].values[0])
    if 'Unifocal' in num_tumor and 'Multifocal' not in num_tumor and 'Multicentric' not in num_tumor:
        Clinical_features.append(torch.tensor([1, 0, 0]))
    elif 'Multifocal' in num_tumor and 'Multicentric' not in num_tumor and 'Unifocal' not in num_tumor:
        Clinical_features.append(torch.tensor([0, 1, 0]))
    elif 'Multicentric' in num_tumor and 'Multifocal' not in num_tumor and 'Unifocal' not in num_tumor:
        Clinical_features.append(torch.tensor([0, 0, 1]))
    else:
        Clinical_features.append(torch.tensor([0, 0, 0]))

    Preoperative_mass_position = str(metadata_df.loc[metadata_df['ID'] == ID, 'Location(nine)'].values[0])
    P_mass_p_list = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    if 'UQ' in Preoperative_mass_position:
        P_mass_p_list[0] = 1
    if 'OQ' in Preoperative_mass_position:
        P_mass_p_list[1] = 1
    if 'LQ' in Preoperative_mass_position:
        P_mass_p_list[2] = 1
    if 'IQ' in Preoperative_mass_position:
        P_mass_p_list[3] = 1
    if 'UOQ' in Preoperative_mass_position:
        P_mass_p_list[4] = 1
    if 'LOQ' in Preoperative_mass_position:
        P_mass_p_list[5] = 1
    if 'LIQ' in Preoperative_mass_position:
        P_mass_p_list[6] = 1
    if 'UIQ' in Preoperative_mass_position:
        P_mass_p_list[7] = 1
    if 'CenP' in Preoperative_mass_position:
        P_mass_p_list[8] = 1
    Clinical_features.append(torch.tensor(P_mass_p_list))

    cT_stage = str(metadata_df.loc[metadata_df['ID'] == ID, 'cT'].values[0])
    if 'T0' in cT_stage:
        Clinical_features.append(torch.tensor([1, 0, 0, 0, 0]))
    elif 'T1' in cT_stage:
        Clinical_features.append(torch.tensor([0, 1, 0, 0, 0]))
    elif 'T2' in cT_stage:
        Clinical_features.append(torch.tensor([0, 0, 1, 0, 0]))
    elif 'T3' in cT_stage:
        Clinical_features.append(torch.tensor([0, 0, 0, 1, 0]))
    elif 'T4' in cT_stage:
        Clinical_features.append(torch.tensor([0, 0, 0, 0, 1]))
    else:
        Clinical_features.append(torch.tensor([0, 0, 0, 0, 0]))

    Clinical_features.append(torch.tensor([0, 1, 0, 0]))

    calcify_MG = str(metadata_df.loc[metadata_df['ID'] == ID, 'Calcification'].values[0])
    if 'Yes' in calcify_MG:
        Clinical_features.append(torch.tensor([1]))
    elif 'No' in calcify_MG:
        Clinical_features.append(torch.tensor([-1]))
    else:
        Clinical_features.append(torch.tensor([0]))

    density_MG = str(metadata_df.loc[metadata_df['ID'] == ID, 'Breast density '].values[0])
    if 'A' in density_MG:
        Clinical_features.append(torch.tensor([1, 0, 0, 0]))
    elif 'B' in density_MG:
        Clinical_features.append(torch.tensor([0, 1, 0, 0]))
    elif 'C' in density_MG:
        Clinical_features.append(torch.tensor([0, 0, 1, 0]))
    elif 'D' in density_MG:
        Clinical_features.append(torch.tensor([0, 0, 0, 1]))
    else:
        Clinical_features.append(torch.tensor([0, 0, 0, 0]))


    for feature_name in ['Age', 'Tumor size MRI ']:
        feature_value = float(metadata_df.loc[metadata_df['ID'] == ID, feature_name].values[0])
        if np.isnan(feature_value):
            Clinical_features.append(torch.tensor([mean_std_dict[feature_name][0]]))
        else:
            feature_value = (feature_value - mean_std_dict[feature_name][0]) / mean_std_dict[feature_name][1]
            Clinical_features.append(torch.tensor([feature_value]))
    for feature_name in ['max diameter with lowest layer of ALN']:
        feature_value = float(metadata_df.loc[metadata_df['ID'] == ID, feature_name].values[0])
        if np.isnan(feature_value):
            feature_value = 0
            Clinical_features.append(torch.tensor([feature_value]))
        else:
            Clinical_features.append(torch.tensor([feature_value]))
    return torch.cat(Clinical_features)

def Extract_pathology_features(metadata_df, ID):
    Clinical_features = []
    pathological_types = str(metadata_df.loc[metadata_df['ID'] == ID, 'Histological type  (needle biopsy)'].values[0])
    if 'Invasive ductal carcinoma' in pathological_types:
        Clinical_features.append(torch.tensor([1, 0, 0, 0, 0, 0, 0, 0]))
    elif 'Invasive lobular carcinoma' in pathological_types:
        Clinical_features.append(torch.tensor([0, 1, 0, 0, 0, 0, 0, 0]))
    elif 'Invasive carcinoma' in pathological_types:
        Clinical_features.append(torch.tensor([0, 0, 0, 1, 0, 0, 0, 0]))
    elif 'Invasive micropapillary carcinoma' in pathological_types:
        Clinical_features.append(torch.tensor([0, 0, 0, 0, 0, 1, 0, 0]))
    elif 'Ductal carcinoma in situ' in pathological_types:
        Clinical_features.append(torch.tensor([0, 0, 0, 0, 0, 0, 1, 0]))
    else:
        Clinical_features.append(torch.tensor([0, 0, 0, 0, 0, 0, 0, 0]))

    histological_grading = str(metadata_df.loc[metadata_df['ID'] == ID, 'Histological grade '].values[0])
    if 'I' in histological_grading and 'II' not in histological_grading and 'III' not in histological_grading:
        Clinical_features.append(torch.tensor([1, 0, 0]))
    elif 'II' in histological_grading and 'III' not in histological_grading and 'I' not in histological_grading:
        Clinical_features.append(torch.tensor([0, 1, 0]))
    elif 'III' in histological_grading and 'I' not in histological_grading and 'II' not in histological_grading:
        Clinical_features.append(torch.tensor([0, 0, 1]))
    else:
        Clinical_features.append(torch.tensor([0, 0, 0]))

    ER = str(metadata_df.loc[metadata_df['ID'] == ID, 'ER'].values[0])
    if '-' in ER:
        Clinical_features.append(torch.tensor([1, 0]))
    elif '+' in ER:
        Clinical_features.append(torch.tensor([0, 1]))
    else:
        Clinical_features.append(torch.tensor([0, 0]))
    
    PR = str(metadata_df.loc[metadata_df['ID'] == ID, 'PR'].values[0])
    if '-' in PR:
        Clinical_features.append(torch.tensor([1, 0]))
    elif '+' in PR:
        Clinical_features.append(torch.tensor([0, 1]))
    else:
        Clinical_features.append(torch.tensor([0, 0]))
    
    HER2 = str(metadata_df.loc[metadata_df['ID'] == ID, 'HER2'].values[0])
    if '-' in HER2:
        Clinical_features.append(torch.tensor([1, 0]))
    elif '+' in HER2:
        Clinical_features.append(torch.tensor([0, 1]))
    else:
        Clinical_features.append(torch.tensor([0, 0]))

    LVIQF = str(metadata_df.loc[metadata_df['ID'] == ID, 'LVI'].values[0])
    if 'Absent' in LVIQF:
        Clinical_features.append(torch.tensor([1, 0]))
    elif 'Present' in LVIQF:
        Clinical_features.append(torch.tensor([0, 1]))
    else:
        Clinical_features.append(torch.tensor([0, 0]))

    for feature_name in ['Ki67']:
        feature_value = str(metadata_df.loc[metadata_df['ID'] == ID, feature_name].values[0])
        if '-' in feature_value or '<20%' in feature_value:
            Clinical_features.append(torch.tensor([float(0)]))
        elif '+' in feature_value or '>=20%' in feature_value:
            Clinical_features.append(torch.tensor([float(1)]))
        else:
            Clinical_features.append(torch.tensor([float(0.5)]))
    for feature_name in ['SLN-positive', 'total SLN', 'Positive_Total_SLN_ratio']:
        feature_value = float(metadata_df.loc[metadata_df['ID'] == ID, feature_name].values[0])
        if np.isnan(feature_value):
            Clinical_features.append(torch.tensor([mean_std_dict[feature_name][0]]))
        else:
            feature_value = (feature_value - mean_std_dict[feature_name][0]) / mean_std_dict[feature_name][1]
            Clinical_features.append(torch.tensor([feature_value]))
    return torch.cat(Clinical_features)

# 1
class Dataset_img_clinical(Dataset):
    def __init__(self, data_dir, split_path, data_set='train', augment=True):
        self.data_dir = data_dir
        split_data = pickle.load(open(split_path, 'rb'))
        self.ID_list = split_data[data_set]
        self.augment = augment
        self.df = pd.read_excel(os.path.join(data_dir, 'CP.xlsx'), sheet_name='Sheet1', dtype={'ID': str})
        self.df['ID'] = self.df['ID'].astype(str)

        if augment:
            self.transforms_2D = Compose([
                Rand2DElasticd(keys=['img', 'mask'], spacing=(20, 20), magnitude_range=(1, 2), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_x=np.pi / 360 * 30, prob=0.3, keep_size=True,
                           mode="nearest", padding_mode="zeros"),
            ])
            self.transforms_3D = Compose([
                Rand3DElasticd(keys=['img', 'mask'], sigma_range=(5, 7), magnitude_range=(10, 20), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_z=np.pi / 360 * 30, prob=0.3, keep_size=True,
                            mode="nearest", padding_mode="zeros"),
            ])
        self.len = len(self.ID_list)

    def __getitem__(self, idx):
        ID = self.ID_list[idx]['ID']
        label = self.ID_list[idx]['label']
        print(ID)
        
        MR_DCE, _, _, _ = NiiDataRead(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, '{}_DCE_N4.nii*'.format(ID)))[0])
        if MR_DCE.max() < 0:
            MR_DCE = masked_Zscore_norm(MR_DCE, mask_min=np.min(MR_DCE), mask_max=np.max(MR_DCE), percentile_min=None,
                                        percentile_max=99.5)
        else:
            MR_DCE = masked_Zscore_norm(MR_DCE, mask_min=0, mask_max=np.max(MR_DCE), percentile_min=None,
                                        percentile_max=99.5)
        MR_DCE_decay_mask, _, _, _ = NiiDataRead(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, '{}_DCE_decay1.nii*'.format(ID)))[0])
        
        img_MR_DCE = MR_DCE[np.newaxis, ...]  # (1, D, H, W)
        mask_MR_DCE = MR_DCE_decay_mask[np.newaxis, ...]  # (1, D, H, W)
        
        img_MR_DCE = transform.resize(img_MR_DCE, (1, 144, 320, 320), order=0, mode='constant', clip=False,
                                      preserve_range=True, anti_aliasing=False)
        mask_MR_DCE = transform.resize(mask_MR_DCE, (1, 144, 320, 320), order=0, mode='constant', clip=False,
                                       preserve_range=True, anti_aliasing=False)
        
        MG_MLO, _, _, _ = NiiDataRead_2D(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, 'MG', '*{}_*MLO.nii*'.format(ID)))[0])
        if MG_MLO.max() <= 4095:
            MG_MLO = masked_Zscore_norm(MG_MLO, mask_min=0, mask_max=np.max(MG_MLO), percentile_min=0.5,
                                       percentile_max=99.5)
        else:
            MG_MLO = masked_Zscore_norm(MG_MLO, mask_min=5000, mask_max=10000, percentile_min=0.5,
                                       percentile_max=99.5)
        
        MG_MLO_decay_mask, _, _, _ = NiiDataRead_2D(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, 'MG', '*{}_*MLO_decay1.nii*'.format(ID)))[0])
        
        img_MG_MLO = MG_MLO[np.newaxis, ...]  # (1, H, W)
        mask_MG_MLO = MG_MLO_decay_mask[np.newaxis, ...]  # (1, H, W)
        
        img_MG_MLO = transform.resize(img_MG_MLO, (1, 640, 512), order=0, mode='constant', clip=False,
                                      preserve_range=True, anti_aliasing=False)
        mask_MG_MLO = transform.resize(mask_MG_MLO, (1, 640, 512), order=0, mode='constant', clip=False,
                                       preserve_range=True, anti_aliasing=False)

        Clinical_features = Extract_clinical_features(self.df, ID)
        pathology_features = Extract_pathology_features(self.df, ID)

        if self.augment:
            augmented_MR_DCE = self.transforms_3D({'img': img_MR_DCE, 'mask': mask_MR_DCE})
            img_MR_DCE = augmented_MR_DCE['img']
            mask_MR_DCE = augmented_MR_DCE['mask']
            
            augmented_MG_MLO = self.transforms_2D({'img': img_MG_MLO, 'mask': mask_MG_MLO})
            img_MG_MLO = augmented_MG_MLO['img']
            mask_MG_MLO = augmented_MG_MLO['mask']
            
            Clinical_features += torch.randn(*Clinical_features.size()) * 0.05
            pathology_features += torch.randn(*pathology_features.size()) * 0.05
        
        img_MR_DCE = np.concatenate((img_MR_DCE, mask_MR_DCE), axis=0)  # (2, 144, 320, 320)
        img_MG_MLO = np.concatenate((img_MG_MLO, mask_MG_MLO), axis=0)  # (2, 640, 512)

        img_MR_DCE = torch.from_numpy(img_MR_DCE).float()
        img_MG_MLO = torch.from_numpy(img_MG_MLO).float()
        
        if label == 'Positive':
            label = torch.tensor(1)
        else:
            label = torch.tensor(0)
            
        return ID, img_MR_DCE, img_MG_MLO, Clinical_features, pathology_features, label

    def __len__(self):
        return self.len


class Dataset_img_clinical_onlyCP(Dataset):
    def __init__(self, data_dir, split_path, data_set='train', augment=True):
        self.data_dir = data_dir
        split_data = pickle.load(open(split_path, 'rb'))
        self.ID_list = split_data[data_set]
        self.augment = augment
        self.df = pd.read_excel(os.path.join(data_dir, 'CP.xlsx'), sheet_name='Sheet1', dtype={'ID': str})
        self.df['ID'] = self.df['ID'].astype(str)

        if augment:
            self.transforms_2D = Compose([
                Rand2DElasticd(keys=['img', 'mask'], spacing=(20, 20), magnitude_range=(1, 2), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_x=np.pi / 360 * 30, prob=0.3, keep_size=True,
                           mode="nearest", padding_mode="zeros"),
            ])
            self.transforms_3D = Compose([
                Rand3DElasticd(keys=['img', 'mask'], sigma_range=(5, 7), magnitude_range=(10, 20), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_z=np.pi / 360 * 30, prob=0.3, keep_size=True,
                            mode="nearest", padding_mode="zeros"),
            ])
        self.len = len(self.ID_list)

    def __getitem__(self, idx):
        ID = self.ID_list[idx]['ID']
        label = self.ID_list[idx]['label']
        print(ID)
        
        Clinical_features = Extract_clinical_features(self.df, ID)
        pathology_features = Extract_pathology_features(self.df, ID)

        if self.augment:
            
            Clinical_features += torch.randn(*Clinical_features.size()) * 0.05
            pathology_features += torch.randn(*pathology_features.size()) * 0.05
        
        if label == 'Positive':
            label = torch.tensor(1)
        else:
            label = torch.tensor(0)
            
        return ID, Clinical_features, pathology_features, label

    def __len__(self):
        return self.len


class Dataset_img_clinical_DCE(Dataset):
    def __init__(self, data_dir, split_path, data_set='train', augment=True):
        self.data_dir = data_dir
        split_data = pickle.load(open(split_path, 'rb'))
        self.ID_list = split_data[data_set]
        self.augment = augment
        self.df = pd.read_excel(os.path.join(data_dir, 'CP.xlsx'), sheet_name='Sheet1', dtype={'ID': str})
        self.df['ID'] = self.df['ID'].astype(str)

        if augment:
            self.transforms_2D = Compose([
                Rand2DElasticd(keys=['img', 'mask'], spacing=(20, 20), magnitude_range=(1, 2), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_x=np.pi / 360 * 30, prob=0.3, keep_size=True,
                           mode="nearest", padding_mode="zeros"),
            ])
            self.transforms_3D = Compose([
                Rand3DElasticd(keys=['img', 'mask'], sigma_range=(5, 7), magnitude_range=(10, 20), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_z=np.pi / 360 * 30, prob=0.3, keep_size=True,
                            mode="nearest", padding_mode="zeros"),
            ])
        self.len = len(self.ID_list)

    def __getitem__(self, idx):
        ID = self.ID_list[idx]['ID']
        label = self.ID_list[idx]['label']
        print(ID)
        
        MR_DCE, _, _, _ = NiiDataRead(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, '{}_DCE_N4.nii*'.format(ID)))[0])
        if MR_DCE.max() < 0:
            MR_DCE = masked_Zscore_norm(MR_DCE, mask_min=np.min(MR_DCE), mask_max=np.max(MR_DCE), percentile_min=None,
                                        percentile_max=99.5)
        else:
            MR_DCE = masked_Zscore_norm(MR_DCE, mask_min=0, mask_max=np.max(MR_DCE), percentile_min=None,
                                        percentile_max=99.5)
        MR_DCE_decay_mask, _, _, _ = NiiDataRead(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, '{}_DCE_decay1.nii*'.format(ID)))[0])
        
        img_MR_DCE = MR_DCE[np.newaxis, ...]  # (1, D, H, W)
        mask_MR_DCE = MR_DCE_decay_mask[np.newaxis, ...]  # (1, D, H, W)
        
        img_MR_DCE = transform.resize(img_MR_DCE, (1, 144, 320, 320), order=0, mode='constant', clip=False,
                                      preserve_range=True, anti_aliasing=False)
        mask_MR_DCE = transform.resize(mask_MR_DCE, (1, 144, 320, 320), order=0, mode='constant', clip=False,
                                       preserve_range=True, anti_aliasing=False)
        
        if self.augment:
            augmented_MR_DCE = self.transforms_3D({'img': img_MR_DCE, 'mask': mask_MR_DCE})
            img_MR_DCE = augmented_MR_DCE['img']
            mask_MR_DCE = augmented_MR_DCE['mask']
            
        img_MR_DCE = np.concatenate((img_MR_DCE, mask_MR_DCE), axis=0)  # (2, 144, 320, 320)

        img_MR_DCE = torch.from_numpy(img_MR_DCE).float()
        
        if label == 'Positive':
            label = torch.tensor(1)
        else:
            label = torch.tensor(0)
            
        return ID, img_MR_DCE, label

    def __len__(self):
        return self.len



class Dataset_img(Dataset):
    def __init__(self, data_dir, split_path, data_set='train', augment=True):
        self.data_dir = data_dir
        split_data = pickle.load(open(split_path, 'rb'))
        self.ID_list = split_data[data_set]
        self.augment = augment
        self.df = pd.read_excel(os.path.join(data_dir, 'CP.xlsx'), sheet_name='Sheet1', dtype={'ID': str})
        self.df['ID'] = self.df['ID'].astype(str)

        if augment:
            self.transforms_2D = Compose([
                Rand2DElasticd(keys=['img', 'mask'], spacing=(20, 20), magnitude_range=(1, 2), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_x=np.pi / 360 * 30, prob=0.3, keep_size=True,
                           mode="nearest", padding_mode="zeros"),
            ])
            self.transforms_3D = Compose([
                Rand3DElasticd(keys=['img', 'mask'], sigma_range=(5, 7), magnitude_range=(10, 20), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_z=np.pi / 360 * 30, prob=0.3, keep_size=True,
                            mode="nearest", padding_mode="zeros"),
            ])
        self.len = len(self.ID_list)

    def __getitem__(self, idx):
        ID = self.ID_list[idx]['ID']
        label = self.ID_list[idx]['label']
        print(ID)
        
        MR_DCE, _, _, _ = NiiDataRead(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, '{}_DCE_N4.nii*'.format(ID)))[0])
        if MR_DCE.max() < 0:
            MR_DCE = masked_Zscore_norm(MR_DCE, mask_min=np.min(MR_DCE), mask_max=np.max(MR_DCE), percentile_min=None,
                                        percentile_max=99.5)
        else:
            MR_DCE = masked_Zscore_norm(MR_DCE, mask_min=0, mask_max=np.max(MR_DCE), percentile_min=None,
                                        percentile_max=99.5)
        MR_DCE_decay_mask, _, _, _ = NiiDataRead(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, '{}_DCE_decay1.nii*'.format(ID)))[0])
        
        img_MR_DCE = MR_DCE[np.newaxis, ...]  # (1, D, H, W)
        mask_MR_DCE = MR_DCE_decay_mask[np.newaxis, ...]  # (1, D, H, W)
        
        img_MR_DCE = transform.resize(img_MR_DCE, (1, 144, 320, 320), order=0, mode='constant', clip=False,
                                      preserve_range=True, anti_aliasing=False)
        mask_MR_DCE = transform.resize(mask_MR_DCE, (1, 144, 320, 320), order=0, mode='constant', clip=False,
                                       preserve_range=True, anti_aliasing=False)
        
        MG_MLO, _, _, _ = NiiDataRead_2D(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, 'MG', '*{}_*MLO.nii*'.format(ID)))[0])
        if MG_MLO.max() <= 4095:
            MG_MLO = masked_Zscore_norm(MG_MLO, mask_min=0, mask_max=np.max(MG_MLO), percentile_min=0.5,
                                       percentile_max=99.5)
        else:
            MG_MLO = masked_Zscore_norm(MG_MLO, mask_min=5000, mask_max=10000, percentile_min=0.5,
                                       percentile_max=99.5)
        
        MG_MLO_decay_mask, _, _, _ = NiiDataRead_2D(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, 'MG', '*{}_*MLO_decay1.nii*'.format(ID)))[0])
        
        img_MG_MLO = MG_MLO[np.newaxis, ...]  # (1, H, W)
        mask_MG_MLO = MG_MLO_decay_mask[np.newaxis, ...]  # (1, H, W)
        
        img_MG_MLO = transform.resize(img_MG_MLO, (1, 640, 512), order=0, mode='constant', clip=False,
                                      preserve_range=True, anti_aliasing=False)
        mask_MG_MLO = transform.resize(mask_MG_MLO, (1, 640, 512), order=0, mode='constant', clip=False,
                                       preserve_range=True, anti_aliasing=False)

        if self.augment:
            augmented_MR_DCE = self.transforms_3D({'img': img_MR_DCE, 'mask': mask_MR_DCE})
            img_MR_DCE = augmented_MR_DCE['img']
            mask_MR_DCE = augmented_MR_DCE['mask']
            
            augmented_MG_MLO = self.transforms_2D({'img': img_MG_MLO, 'mask': mask_MG_MLO})
            img_MG_MLO = augmented_MG_MLO['img']
            mask_MG_MLO = augmented_MG_MLO['mask']
            
        img_MR_DCE = np.concatenate((img_MR_DCE, mask_MR_DCE), axis=0)  # (2, 144, 320, 320)
        img_MG_MLO = np.concatenate((img_MG_MLO, mask_MG_MLO), axis=0)  # (2, 640, 512)

        img_MR_DCE = torch.from_numpy(img_MR_DCE).float()
        img_MG_MLO = torch.from_numpy(img_MG_MLO).float()
        
        if label == 'Positive':
            label = torch.tensor(1)
        else:
            label = torch.tensor(0)
            
        return ID, img_MR_DCE, img_MG_MLO, label

    def __len__(self):
        return self.len



class Dataset_img_clinical_org(Dataset):
    def __init__(self, data_dir, split_path,data_set='train', augment=True):

        self.data_dir = data_dir
        split_data = pickle.load(open(split_path, 'rb'))
        self.ID_list = split_data[data_set]
        self.augment = augment
        self.df = pd.read_excel(os.path.join(data_dir,'CP.xlsx'), sheet_name='Sheet1', dtype={'ID': str})
        self.df['ID'] = self.df['ID'].astype(str)

        if augment:
            self.transforms_2D = Compose([
                Rand2DElasticd(keys=['img', 'mask'], spacing=(20, 20), magnitude_range=(1, 2), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_x=np.pi / 360 * 30, prob=0.3, keep_size=True,
                           mode="nearest", padding_mode="zeros"),
            ])
            self.transforms_3D = Compose([
                Rand3DElasticd(keys=['img', 'mask'], sigma_range=(5, 7), magnitude_range=(10, 20), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_z=np.pi / 360 * 30, prob=0.3, keep_size=True,
                            mode="nearest", padding_mode="zeros"),
            ])
        self.len = len(self.ID_list)

    def __getitem__(self, idx):

        ID = self.ID_list[idx]['ID']
        label = self.ID_list[idx]['label']
        print(ID)
        MR_DCE, _, _, _ = NiiDataRead(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, '{}_DCE_N4.nii*'.format(ID)))[0])
        if MR_DCE.max() < 0:
            MR_DCE = masked_Zscore_norm(MR_DCE, mask_min=np.min(MR_DCE), mask_max=np.max(MR_DCE), percentile_min=None,
                                        percentile_max=99.5)
        else:
            MR_DCE = masked_Zscore_norm(MR_DCE, mask_min=0, mask_max=np.max(MR_DCE), percentile_min=None,
                                        percentile_max=99.5)
        MR_DCE_GTV, _, _, _ = NiiDataRead(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, '{}_DCE_GTV.nii*'.format(ID)))[0])
        MR_DCE_GTV[MR_DCE_GTV <= 0.5] = 0
        MR_DCE_GTV[MR_DCE_GTV > 0.5] = 1
        MR_DCE_GTVnd1, _, _, _ = NiiDataRead(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, '{}_DCE_GTVnd1.nii*'.format(ID)))[0])
        MR_DCE_GTVnd1[MR_DCE_GTVnd1 <= 0.5] = 0
        MR_DCE_GTVnd1[MR_DCE_GTVnd1 > 0.5] = 1
        img_MR_DCE = MR_DCE[np.newaxis, ...]
        mask_MR_DCE = np.concatenate((MR_DCE_GTV[np.newaxis, ...], MR_DCE_GTVnd1[np.newaxis, ...]), axis=0)
        img_MR_DCE = transform.resize(img_MR_DCE, (1, 144, 320, 320), order=0, mode='constant', clip=False,
                                          preserve_range=True, anti_aliasing=False)
        mask_MR_DCE = transform.resize(mask_MR_DCE, (2, 144, 320, 320), order=0, mode='constant', clip=False,
                                           preserve_range=True, anti_aliasing=False)
        MG_MLO, _, _, _ = NiiDataRead_2D(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, 'MG', '*{}_*MLO.nii*'.format(ID)))[0])
        if MG_MLO.max() <= 4095:
            MG_MLO = masked_Zscore_norm(MG_MLO, mask_min=0, mask_max=np.max(MG_MLO), percentile_min=0.5,
                                       percentile_max=99.5)
        else:
            MG_MLO = masked_Zscore_norm(MG_MLO, mask_min=5000, mask_max=10000, percentile_min=0.5,
                                       percentile_max=99.5)
        MG_MLO_GTV, _, _, _ = NiiDataRead_2D(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, 'MG', '*{}_*MLO_GTV.nii*'.format(ID)))[0])
        MG_MLO_GTV[MG_MLO_GTV <= 0.5] = 0
        MG_MLO_GTV[MG_MLO_GTV > 0.5] = 1
        MG_MLO_GTVnd1, _, _, _ = NiiDataRead_2D(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, 'MG', '*{}_*MLO_GTVnd1.nii*'.format(ID)))[0])
        MG_MLO_GTVnd1[MG_MLO_GTVnd1 <= 0.5] = 0
        MG_MLO_GTVnd1[MG_MLO_GTVnd1 > 0.5] = 1
        MG_MLO = transform.resize(MG_MLO, (640, 512), order=0, mode='constant', clip=False,
                                     preserve_range=True, anti_aliasing=False)
        MG_MLO_GTV = transform.resize(MG_MLO_GTV, (640, 512), order=0, mode='constant', clip=False,
                                      preserve_range=True, anti_aliasing=False)
        MG_MLO_GTVnd1 = transform.resize(MG_MLO_GTVnd1, (640, 512), order=0, mode='constant', clip=False,
                                      preserve_range=True, anti_aliasing=False)
        img_MG_MLO = MG_MLO[np.newaxis, ...]
        mask_MG_MLO = np.concatenate((MG_MLO_GTV[np.newaxis, ...], MG_MLO_GTVnd1[np.newaxis, ...]), axis=0)

        Clinical_features = Extract_clinical_features(self.df, ID)
        pathology_features = Extract_pathology_features(self.df, ID)

        if self.augment:

            augmented_MR_DCE = self.transforms_3D({'img': img_MR_DCE, 'mask': mask_MR_DCE})
            img_MR_DCE = np.concatenate((augmented_MR_DCE['img'], augmented_MR_DCE['mask']), axis=0)

            augmented_MG_MLO = self.transforms_2D({'img': img_MG_MLO, 'mask': mask_MG_MLO})
            img_MG_MLO = np.concatenate((augmented_MG_MLO['img'], augmented_MG_MLO['mask']), axis=0)
            
            Clinical_features += torch.randn(*Clinical_features.size()) * 0.05
            pathology_features += torch.randn(*pathology_features.size()) * 0.05
        else:
            img_MR_DCE = np.concatenate((img_MR_DCE, mask_MR_DCE), axis=0)
            img_MG_MLO = np.concatenate((img_MG_MLO, mask_MG_MLO), axis=0)


        img_MR_DCE = torch.from_numpy(img_MR_DCE)
        img_MG_MLO = torch.from_numpy(img_MG_MLO)
        if label == 'Positive':
            label = torch.tensor(1)
        else:
            label = torch.tensor(0)
        return ID, img_MR_DCE, img_MG_MLO, Clinical_features, pathology_features, label

    def __len__(self):
        return self.len


class Dataset_img_clinical_MGMLO(Dataset):
    def __init__(self, data_dir, split_path, data_set='train', augment=True):
        self.data_dir = data_dir
        split_data = pickle.load(open(split_path, 'rb'))
        self.ID_list = split_data[data_set]
        self.augment = augment
        self.df = pd.read_excel(os.path.join(data_dir, 'CP.xlsx'), sheet_name='Sheet1', dtype={'ID': str})
        self.df['ID'] = self.df['ID'].astype(str)

        if augment:
            self.transforms_2D = Compose([
                Rand2DElasticd(keys=['img', 'mask'], spacing=(20, 20), magnitude_range=(1, 2), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_x=np.pi / 360 * 30, prob=0.3, keep_size=True,
                           mode="nearest", padding_mode="zeros"),
            ])
            self.transforms_3D = Compose([
                Rand3DElasticd(keys=['img', 'mask'], sigma_range=(5, 7), magnitude_range=(10, 20), mode="nearest",
                               padding_mode="zeros", prob=0.2),
                RandGaussianNoised(keys=['img'], mean=0.0, std=0.1, prob=0.1),
                RandRotated(keys=['img', 'mask'], range_z=np.pi / 360 * 30, prob=0.3, keep_size=True,
                            mode="nearest", padding_mode="zeros"),
            ])
        self.len = len(self.ID_list)

    def __getitem__(self, idx):
        ID = self.ID_list[idx]['ID']
        label = self.ID_list[idx]['label']
        print(ID)
        MG_MLO, _, _, _ = NiiDataRead_2D(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, 'MG', '*{}_*MLO.nii*'.format(ID)))[0])
        if MG_MLO.max() <= 4095:
            MG_MLO = masked_Zscore_norm(MG_MLO, mask_min=0, mask_max=np.max(MG_MLO), percentile_min=0.5,
                                       percentile_max=99.5)
        else:
            MG_MLO = masked_Zscore_norm(MG_MLO, mask_min=5000, mask_max=10000, percentile_min=0.5,
                                       percentile_max=99.5)
        
        MG_MLO_decay_mask, _, _, _ = NiiDataRead_2D(glob.glob(
            os.path.join(self.data_dir, 'MRMG', label, ID, 'MG', '*{}_*MLO_decay1.nii*'.format(ID)))[0])
        
        img_MG_MLO = MG_MLO[np.newaxis, ...]  # (1, H, W)
        mask_MG_MLO = MG_MLO_decay_mask[np.newaxis, ...]  # (1, H, W)
        
        img_MG_MLO = transform.resize(img_MG_MLO, (1, 640, 512), order=0, mode='constant', clip=False,
                                      preserve_range=True, anti_aliasing=False)
        mask_MG_MLO = transform.resize(mask_MG_MLO, (1, 640, 512), order=0, mode='constant', clip=False,
                                       preserve_range=True, anti_aliasing=False)

        if self.augment:
            augmented_MG_MLO = self.transforms_2D({'img': img_MG_MLO, 'mask': mask_MG_MLO})
            img_MG_MLO = augmented_MG_MLO['img']
            mask_MG_MLO = augmented_MG_MLO['mask']
            
        img_MG_MLO = np.concatenate((img_MG_MLO, mask_MG_MLO), axis=0)  # (2, 640, 512)

        img_MG_MLO = torch.from_numpy(img_MG_MLO).float()
        
        if label == 'Positive':
            label = torch.tensor(1)
        else:
            label = torch.tensor(0)
            
        return ID, img_MG_MLO, label

    def __len__(self):
        return self.len



if __name__ == '__main__':
    print('-----------------')