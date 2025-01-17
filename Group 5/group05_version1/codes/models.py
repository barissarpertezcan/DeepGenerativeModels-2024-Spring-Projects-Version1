import torch
import torch.nn as nn
import os

from codes.layers import StyleTransformerEncoder, StyleTransformerDecoder

from codes.utils import download_swin_and_create_cutted_model
from einops import rearrange

project_absolute_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class StyleTransformer(nn.Module):
    """
    A StyleTransformer that iteratively processes style and content through multiple encoder and decoder blocks.

    Args:
        dim (int): Number of input channels.
        input_resolution (tuple[int, int]): Dimensions (height, width) of the input feature map.
        num_heads (int): Number of attention heads.
        window_size (int): Size of the attention window.
        mlp_ratio (float): Expansion ratio for the MLP block compared to the number of input channels.
        qk_scale (float | None, optional): Custom scaling factor for query-key dot products in attention mechanisms.
        act_layer (nn.Module, optional): Activation function used in the MLP block. Defaults to nn.ReLU.
    """
    def __init__(self, dim, input_resolution, num_heads, window_size=8, shifted=True, mlp_ratio=4., act_layer=nn.ReLU):
        super().__init__()

        self.dim = dim
        self.input_resolution = input_resolution
        self.encoder = StyleTransformerEncoder(dim, num_heads, window_size, shifted, mlp_ratio, act_layer)
        self.decoder = StyleTransformerDecoder(dim, num_heads, window_size, shifted, mlp_ratio, act_layer)

    def forward(self, content, style, num_steps=4):
        """
        Args:
            content (torch.Tensor): Content features of shape (B, H, W, C).
            style (torch.Tensor): Initial style features of shape (B, H, W, C).
            num_steps (int): Number of transformation steps to iterate through.

        Returns:
            torch.Tensor: The transformed content features after T steps.
        """
        # change the shape of style and content to (B, H*w, C) from (B, H, W, C)
        content = content.flatten(1, 2).to(content.device)
        style = style.flatten(1, 2).to(style.device)

        # Initialize scale and shift from style
        scale = style.clone()  # Initialize scale from style
        shift = style.clone()  # Initialize shift from style

        for _ in range(num_steps):
            style, scale, shift = self.encoder(style, scale, shift)
            content = self.decoder(content, style, scale, shift)

        # change the shape of content to (B, H, W, C) from (B, H*w, C)
        content = rearrange(content, 'b (h w) c -> b h w c', h=self.input_resolution[0], w=self.input_resolution[1])

        return content


class StyleDecoder(nn.Module):
    """
    StyleTransferDecoder constructs the image from encoded features using upsampling and convolution layers.
    The design follows the architecture described in "Arbitrary Style Transfer in Real-time with Adaptive Instance Normalization"
    by Huang and Belongie. It consists of multiple upsampling and convolution layers to gradually upscale the feature map
    to the target resolution, interspersed with ReLU activation functions to introduce non-linearities.

    References:
    - Huang, X., & Belongie, S. (2017). Arbitrary Style Transfer in Real-time with Adaptive Instance Normalization.
    In Proceedings of the IEEE International Conference on Computer Vision (pp. 1501-1510).
    """

    def __init__(self):
        super().__init__()

        self.decoder = nn.Sequential(
            nn.Conv2d(256, 128, (3, 3), padding=(1, 1), padding_mode='reflect'),
            nn.ReLU(),

            nn.Upsample(scale_factor=2, mode='nearest'),

            nn.Conv2d(128, 128, (3, 3), padding=(1, 1), padding_mode='reflect'),
            nn.ReLU(),

            nn.Conv2d(128, 128, (3, 3), padding=(1, 1), padding_mode='reflect'),
            nn.ReLU(),

            nn.Conv2d(128, 128, (3, 3), padding=(1, 1), padding_mode='reflect'),
            nn.ReLU(),

            nn.Conv2d(128, 64, (3, 3), padding=(1, 1), padding_mode='reflect'),
            nn.ReLU(),

            nn.Upsample(scale_factor=2, mode='nearest'),

            nn.Conv2d(64, 64, (3, 3), padding=(1, 1), padding_mode='reflect'),
            nn.ReLU(),

            nn.Conv2d(64, 32, (3, 3), padding=(1, 1), padding_mode='reflect'),
            nn.ReLU(),
            
            nn.Upsample(scale_factor=2, mode='nearest'),

            nn.Conv2d(32, 32, (3, 3), padding=(1, 1), padding_mode='reflect'),
            nn.ReLU(),

            nn.Conv2d(32, 3, (3, 3), padding=(1, 1), padding_mode='reflect'),
            nn.Sigmoid()
        )

    def forward(self, x):
        """
        Forward pass of the StyleTransferDecoder.

        Args:
            x (torch.Tensor): Input tensor of encoded features from the content and style encoding layer.

        Returns:
            torch.Tensor: Output tensor of the stylized image.
        """
        return self.decoder(x)


class SwinEncoder(torch.nn.Module):
    def __init__(self, relative_model_path="weights/swin_B_first_2_stages.pt", freeze_params=False):
        """
        Initializes the SwinEncoder object which uses the first two stages of the Swin Transformer.

        Args:
        model_path (str, optional): Path where the Swin model is saved or should be saved. Defaults to 'PROJECT_FOLDER/swin_B_first_2_stages.pt'.
        freeze_params (bool): If True, the parameters of the model will be frozen.

        References:
        - Liu, Ze, et al. "Swin Transformer: Hierarchical Vision Transformer using Shifted Windows." arXiv preprint arXiv:2103.14030 (2021). https://arxiv.org/abs/2103.14030
        - Official PyTorch Vision documentation for Swin Transformers: https://pytorch.org/vision/stable/models.html#torchvision.models.swin_transformer
        """
        super().__init__()

        # if swin model is not already saved, download the model, get first 2 stages and save it
        download_swin_and_create_cutted_model(absolute_project_path = project_absolute_path,
                                              model_save_relative_path = relative_model_path)
        
        # Load the model from the specified path
        self.model = torch.load(os.path.join(project_absolute_path, relative_model_path))
        
        if freeze_params:
            self.freeze_parameters()


    def freeze_parameters(self):
        """
        This method sets the requires_grad attribute of all parameters in the model to False,
        effectively freezing the model to prevent any of its weights from being updated.
        """
        for param in self.model.parameters():
            param.requires_grad = False

    def forward(self, x):
        """
        Forward pass through the first two stages of the Swin Transformer.

        Args:
        x (torch.Tensor): Input tensor to be passed through the model.

        Returns:
        torch.Tensor: Output tensor from the model.
        """
        return self.model(x)
