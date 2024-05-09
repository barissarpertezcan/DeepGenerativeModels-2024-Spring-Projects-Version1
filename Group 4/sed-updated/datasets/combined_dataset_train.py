import os
import numpy as np
import torch
from datasets.combined_dataset_base import CombinedDatasetBaseClass
from PIL import Image

class CombinedDatasetTrain(CombinedDatasetBaseClass):
    def __init__(self, *args, **kwargs):
        super(CombinedDatasetTrain, self).__init__(*args, **kwargs)

    def preprocess_image(self, image):
        image = image.transpose(2, 0, 1).astype(np.float32)  # H,W,C -> C,H,W
        image = (image - 127.5) / 127.5  # Normalize (Range: [-1.0, 1.0])
        image = torch.tensor(image, dtype=torch.float32)
        return image

    def crop_image(self, image, crop_height, crop_width, hr_image=True):
        if hr_image:
            return image[crop_height:crop_height + self.image_size, crop_width:crop_width + self.image_size, ...]
        else:
            return image[crop_height:crop_height + self.down_sampled_image_size, crop_width:crop_width + self.down_sampled_image_size, ...]

    def __len__(self):
        return super().__len__()

    def __getitem__(self, index):
        data = dict()
        image_name_hr = self.image_names_hr[index]
        image_name_lr = self.image_names_lr[index]

        image_hr = Image.open(os.path.join(self.image_dir_hr, image_name_hr)).convert('RGB')
        image_lr = Image.open(os.path.join(self.image_dir_lr, image_name_lr)).convert('RGB')

        hr_width, hr_height = image_hr.size
        lr_width, lr_height = image_lr.size

        cropped_height_lr = np.random.randint(0, lr_height - self.down_sampled_image_size + 1)
        cropped_width_lr = np.random.randint(0, lr_width - self.down_sampled_image_size + 1)
        
        cropped_height_hr = cropped_height_lr  * self.down_sample_factor
        cropped_width_hr = cropped_width_lr * self.down_sample_factor

        image_hr_cropped = self.crop_image(np.array(image_hr), cropped_height_hr, cropped_width_hr)
        image_lr_cropped = self.crop_image(np.array(image_lr), cropped_height_lr, cropped_width_lr, hr_image=False)

        image_hr_cropped = self.preprocess_image(image_hr_cropped)
        image_lr_cropped = self.preprocess_image(image_lr_cropped)
        
        data.update({'image_hr': image_hr_cropped, 'image_lr': image_lr_cropped})
        return data
    