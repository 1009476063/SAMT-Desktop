import torch
from ResNet_3D import ResNet18_3D_backbone
from Networks.Classification_Network_2D import Resnet18_backbone
from torch import nn
from Networks.Transformer_Network import Trans_cls_head_base,CNN_cls_head_base
import ssl
ssl._create_default_https_context = ssl._create_unverified_context



class MFNet_CNN_img_pathology_transcat_l3m_orgTransformer_1(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0,clinical_inchannels=32,pathology_inchannels=23):
        super(MFNet_CNN_img_pathology_transcat_l3m_orgTransformer_1, self).__init__()
        self.extractor_MR_DCE = ResNet18_3D_backbone(in_channels=2, no_cuda=no_cuda)
        self.extractor_MG_MLO = Resnet18_backbone(in_channels=2)
        self.last_linear = nn.Linear(2560, n_classes)
        self.MLP_cln = nn.Sequential(
            nn.Linear(clinical_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=False)
        )
        self.MLP_pathology = nn.Sequential(
            nn.Linear(pathology_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=False)
        )
        self.Trans = CNN_cls_head_base(d_model=256, num_classes=n_classes, nhead=4, num_layers=1,
                                         dim_feedforward=1024,
                                         dropout=drop, activation='relu')

    def forward(self, img_MR_DCE, img_MG_MLO, cln, pathology):
        clinical = self.MLP_cln(cln)
        pathgy = self.MLP_pathology(pathology)
        img_MR_DCE = self.extractor_MR_DCE(img_MR_DCE)
        img_MG_MLO = self.extractor_MG_MLO(img_MG_MLO)
        x = torch.cat((img_MR_DCE.unsqueeze(1), img_MG_MLO.unsqueeze(1),
                       clinical.unsqueeze(1), pathgy.unsqueeze(1)), dim=1)
        x = self.Trans(x)
        return img_MR_DCE,img_MG_MLO,clinical,pathgy,x


class MFNet_MGMLO_transcat_l3m_orgTransformer_1(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0):
        super(MFNet_MGMLO_transcat_l3m_orgTransformer_1, self).__init__()
        self.extractor_MG_MLO = Resnet18_backbone(in_channels=2)
        self.Trans = Trans_cls_head_base(d_model=256, num_classes=n_classes, nhead=4, num_layers=1,
                                         dim_feedforward=1024,
                                         dropout=drop, activation='relu')

    def forward(self, img_MG_MLO):
        img_MG_MLO = self.extractor_MG_MLO(img_MG_MLO)
        x = img_MG_MLO.unsqueeze(1)
        x = self.Trans(x)
        return img_MG_MLO,x
class MFNet_img_transcat_l3m_orgTransformer_1(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0):
        super(MFNet_img_transcat_l3m_orgTransformer_1, self).__init__()
        self.extractor_MR_DCE = ResNet18_3D_backbone(in_channels=2, no_cuda=no_cuda)
        self.extractor_MG_MLO = Resnet18_backbone(in_channels=2)
        self.Trans = Trans_cls_head_base(d_model=256, num_classes=n_classes, nhead=4, num_layers=1,
                                         dim_feedforward=1024,
                                         dropout=drop, activation='relu')

    def forward(self, img_MR_DCE, img_MG_MLO):
        img_MR_DCE = self.extractor_MR_DCE(img_MR_DCE)
        img_MG_MLO = self.extractor_MG_MLO(img_MG_MLO)
        x = torch.cat((img_MR_DCE.unsqueeze(1), img_MG_MLO.unsqueeze(1)), dim=1)
        x = self.Trans(x)
        return img_MR_DCE,img_MG_MLO,x

class MFNet_img_pathology_transcat_l3m_orgTransformer_1_org(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0,clinical_inchannels=32,pathology_inchannels=23):
        super(MFNet_img_pathology_transcat_l3m_orgTransformer_1_org, self).__init__()
        self.extractor_MR_DCE = ResNet18_3D_backbone(in_channels=3, no_cuda=no_cuda)
        self.extractor_MG_MLO = Resnet18_backbone(in_channels=3)
        self.last_linear = nn.Linear(2560, n_classes)
        self.MLP_cln = nn.Sequential(
            nn.Linear(clinical_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=False)
        )
        self.MLP_pathology = nn.Sequential(
            nn.Linear(pathology_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=False)
        )
        self.Trans = Trans_cls_head_base(d_model=256, num_classes=n_classes, nhead=4, num_layers=1,
                                         dim_feedforward=1024,
                                         dropout=drop, activation='relu')

    def forward(self, img_MR_DCE, img_MG_MLO, cln, pathology):
        clinical = self.MLP_cln(cln)
        pathgy = self.MLP_pathology(pathology)
        img_MR_DCE = self.extractor_MR_DCE(img_MR_DCE)
        img_MG_MLO = self.extractor_MG_MLO(img_MG_MLO)
        x = torch.cat((img_MR_DCE.unsqueeze(1), img_MG_MLO.unsqueeze(1),
                       clinical.unsqueeze(1), pathgy.unsqueeze(1)), dim=1)
        x = self.Trans(x)
        return img_MR_DCE,img_MG_MLO,clinical,pathgy,x


class MFNet_DCE_transcat_l3m_orgTransformer_1(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0):
        super(MFNet_DCE_transcat_l3m_orgTransformer_1, self).__init__()
        self.extractor_MR_DCE = ResNet18_3D_backbone(in_channels=2, no_cuda=no_cuda)
        self.Trans = Trans_cls_head_base(d_model=256, num_classes=n_classes, nhead=4, num_layers=1,
                                         dim_feedforward=1024,
                                         dropout=drop, activation='relu')

    def forward(self, img_MR_DCE):
        img_MR_DCE = self.extractor_MR_DCE(img_MR_DCE)
        x = img_MR_DCE.unsqueeze(1)
        x = self.Trans(x)
        return img_MR_DCE,x

# use
class MFNet_pathology_transcat_l3m_orgTransformer_1(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0,clinical_inchannels=32,pathology_inchannels=23):
        super(MFNet_pathology_transcat_l3m_orgTransformer_1, self).__init__()
        self.MLP_cln = nn.Sequential(
            nn.Linear(clinical_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=False)
        )
        self.MLP_pathology = nn.Sequential(
            nn.Linear(pathology_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=False)
        )
        self.Trans = Trans_cls_head_base(d_model=256, num_classes=n_classes, nhead=4, num_layers=1,
                                         dim_feedforward=1024,
                                         dropout=drop, activation='relu')

    def forward(self, cln, pathology):
        clinical = self.MLP_cln(cln)
        pathgy = self.MLP_pathology(pathology)
        x = torch.cat((clinical.unsqueeze(1), pathgy.unsqueeze(1)), dim=1)
        x = self.Trans(x)
        return clinical,pathgy,x

# use
class MFNet_img_pathology_transcat_l3m_orgTransformer_1(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0,clinical_inchannels=32,pathology_inchannels=23):
        super(MFNet_img_pathology_transcat_l3m_orgTransformer_1, self).__init__()
        self.extractor_MR_DCE = ResNet18_3D_backbone(in_channels=2, no_cuda=no_cuda)
        self.extractor_MG_MLO = Resnet18_backbone(in_channels=2)
        self.last_linear = nn.Linear(2560, n_classes)
        self.MLP_cln = nn.Sequential(
            nn.Linear(clinical_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=False)
        )
        self.MLP_pathology = nn.Sequential(
            nn.Linear(pathology_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=False)
        )
        self.Trans = Trans_cls_head_base(d_model=256, num_classes=n_classes, nhead=4, num_layers=1,
                                         dim_feedforward=1024,
                                         dropout=drop, activation='relu')

    def forward(self, img_MR_DCE, img_MG_MLO, cln, pathology):
        clinical = self.MLP_cln(cln)
        pathgy = self.MLP_pathology(pathology)
        img_MR_DCE = self.extractor_MR_DCE(img_MR_DCE)
        img_MG_MLO = self.extractor_MG_MLO(img_MG_MLO)
        x = torch.cat((img_MR_DCE.unsqueeze(1), img_MG_MLO.unsqueeze(1),
                       clinical.unsqueeze(1), pathgy.unsqueeze(1)), dim=1)
        x = self.Trans(x)
        return img_MR_DCE,img_MG_MLO,clinical,pathgy,x


class MFNet_img_pathology_transcat_l3m_convnext(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0,clinical_inchannels=32,pathology_inchannels=23):
        super(MFNet_img_pathology_transcat_l3m_convnext, self).__init__()
        self.extractor_MR_DCE = ResNet18_3D_backbone(in_channels=2, no_cuda=no_cuda)
        self.extractor_MG_MLO = Resnet18_backbone(in_channels=2)
        self.MLP_cln = nn.Sequential(
            nn.Linear(clinical_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=True)
        )
        self.MLP_pathology = nn.Sequential(
            nn.Linear(pathology_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=True)
        )
        self.channel_adjust = nn.Conv2d(4,3,kernel_size=1)
        self.Trans = convnext_tiny(pretrained=True)
        for m in self.Trans.features.modules():
            if isinstance(m, nn.Conv2d):
                m.stride = (1, 1)
        self.Trans.classifier = nn.Sequential(nn.AdaptiveAvgPool2d(1),
                                              nn.Flatten(),
                                              nn.Linear(768, 256))

        self.mlp_head = nn.Sequential(nn.LayerNorm(256), nn.Linear(256, n_classes))


    def forward(self, img_MR_DCE, img_MG_MLO, cln, pathology):
        clinical = self.MLP_cln(cln)
        pathgy = self.MLP_pathology(pathology)
        img_MR_DCE = self.extractor_MR_DCE(img_MR_DCE)
        img_MG_MLO = self.extractor_MG_MLO(img_MG_MLO)
        x = torch.cat((img_MR_DCE.unsqueeze(1), img_MG_MLO.unsqueeze(1),
                       clinical.unsqueeze(1), pathgy.unsqueeze(1)), dim=1)
        x = x.view(x.size(0), x.size(1), 16, -1)
        x = self.channel_adjust(x)
        # print(x.shape)
        x = self.Trans(x)
        x = self.mlp_head(x)
        return img_MR_DCE,img_MG_MLO,clinical,pathgy,x


class MFNet_img_pathology_transcat_l3m_resnet50(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0,clinical_inchannels=32,pathology_inchannels=23):
        super(MFNet_img_pathology_transcat_l3m_resnet50, self).__init__()
        self.extractor_MR_DCE = ResNet18_3D_backbone(in_channels=2, no_cuda=no_cuda)
        self.extractor_MG_MLO = Resnet18_backbone(in_channels=2)
        self.MLP_cln = nn.Sequential(
            nn.Linear(clinical_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=True)
        )
        self.MLP_pathology = nn.Sequential(
            nn.Linear(pathology_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=True)
        )
        self.Trans = resnet50(pretrained=False)
        self.Trans.conv1 = nn.Conv2d(4,64,kernel_size=7, stride=1, padding=3, bias=False)
        self.Trans.maxpool = nn.Identity()
        self.Trans.fc = nn.Linear(2048, 256)

        self.mlp_head = nn.Sequential(nn.LayerNorm(256), nn.Linear(256, n_classes))


    def forward(self, img_MR_DCE, img_MG_MLO, cln, pathology):
        clinical = self.MLP_cln(cln)
        pathgy = self.MLP_pathology(pathology)
        img_MR_DCE = self.extractor_MR_DCE(img_MR_DCE)
        img_MG_MLO = self.extractor_MG_MLO(img_MG_MLO)
        x = torch.cat((img_MR_DCE.unsqueeze(1), img_MG_MLO.unsqueeze(1),
                       clinical.unsqueeze(1), pathgy.unsqueeze(1)), dim=1)
        x = x.view(x.size(0), x.size(1), 16, -1)   # (B, 4, 256) → (B, 4, 16, 16)
        x = self.Trans(x)
        x = self.mlp_head(x)
        return img_MR_DCE,img_MG_MLO,clinical,pathgy,x
    

class MFNet_img_pathology_transcat_l3m_vgg19(nn.Module):
    def __init__(self, n_classes=2, no_cuda=False,drop=0,clinical_inchannels=32,pathology_inchannels=23):
        super(MFNet_img_pathology_transcat_l3m_vgg19, self).__init__()
        self.extractor_MR_DCE = ResNet18_3D_backbone(in_channels=2, no_cuda=no_cuda)
        self.extractor_MG_MLO = Resnet18_backbone(in_channels=2)
        self.MLP_cln = nn.Sequential(
            nn.Linear(clinical_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=True)
        )
        self.MLP_pathology = nn.Sequential(
            nn.Linear(pathology_inchannels, 256, bias=False), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Linear(256, 256, bias=True)
        )
        vgg = vgg19(pretrained=False).features
        first_conv = nn.Conv2d(4,64, kernel_size=3, padding=1)
        self.Trans = nn.Sequential(first_conv, *list(vgg.children())[1:-1], nn.AdaptiveAvgPool2d(1))

        self.mlp_head = nn.Sequential(nn.LayerNorm(512), nn.Linear(512, n_classes))


    def forward(self, img_MR_DCE, img_MG_MLO, cln, pathology):
        clinical = self.MLP_cln(cln)
        pathgy = self.MLP_pathology(pathology)
        img_MR_DCE = self.extractor_MR_DCE(img_MR_DCE)
        img_MG_MLO = self.extractor_MG_MLO(img_MG_MLO)
        x = torch.cat((img_MR_DCE.unsqueeze(1), img_MG_MLO.unsqueeze(1),
                       clinical.unsqueeze(1), pathgy.unsqueeze(1)), dim=1)
        x = x.view(x.size(0), x.size(1), 16, -1)
        x = self.Trans(x)
        x = x.squeeze(dim=2)
        x = x.squeeze(dim=2)
        x = self.mlp_head(x)
        return img_MR_DCE,img_MG_MLO,clinical,pathgy,x
    
if __name__ == '__main__':
    print('-------------=====')
