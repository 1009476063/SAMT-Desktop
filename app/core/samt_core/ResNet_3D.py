import torch
import os
from torch import nn
from Networks import resnet


class ResNet18_3D_backbone(nn.Module):
    def __init__(self, in_channels, no_cuda=False):
        super(ResNet18_3D_backbone, self).__init__()
        self.model = resnet.resnet18(
            in_channels=in_channels,
            sample_input_W=1,
            sample_input_H=1,
            sample_input_D=1,
            shortcut_type='A',
            no_cuda=no_cuda,
            num_seg_classes=2)
        net_dict = self.model.state_dict()
        pretrain_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Networks', 'resnet_18_23dataset.pth')
        pretrain = torch.load(pretrain_path, map_location='cpu')
        pretrain_dict = {k[7:]: v for k, v in pretrain['state_dict'].items() if k[7:] in net_dict.keys()}
        if in_channels != 1:
            keys_to_remove = ['conv1.weight', 'bn1.weight', 'bn1.bias', 'bn1.running_mean', 'bn1.running_var', 'bn1.num_batches_tracked']
            for key in keys_to_remove:
                pretrain_dict.pop(key, None)
        net_dict.update(pretrain_dict)
        self.model.load_state_dict(net_dict)
        self.model = nn.Sequential(*list(self.model.children())[:-1])
        self.avg_pool = nn.AdaptiveAvgPool3d(output_size=(1, 1, 1))
        self.dim_reduction = nn.Conv3d(512, 256, kernel_size=1, bias=False)


    def forward(self, x):
        x = self.model(x)
        x = self.avg_pool(x)
        # print(x.shape)
        x = self.dim_reduction(x)
        x = x.view(x.size(0), -1)
        return x

if __name__ == '__main__':
    net = ResNet18_3D_backbone(in_channels=4, no_cuda=True)
    a = torch.rand((1, 4, 32, 128, 192))
    b = net(a)
    print(b.shape)
