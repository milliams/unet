import os
import pathlib

import numpy as np
import skimage.io
import skimage.transform
from pandas import Series, DataFrame
from sklearn.model_selection import train_test_split
import tensorflow as tf


def adjust_data(img, mask):
    d_min = img.min()
    d_max = img.max()
    img -= d_min
    img /= d_max - d_min
    mask = mask / 255
    mask[mask > 0.5] = 1
    mask[mask <= 0.5] = 0
    return img, mask


def load_data(input_dir, label_dir, aug_dict):
    input_images = pathlib.Path(input_dir).glob("*")
    label_images = pathlib.Path(label_dir).glob("*")
    input = DataFrame({"image": Series(input_images).apply(str), "mask": Series(label_images).apply(str)})
    train_filenames, test_validate_filenames = train_test_split(input, test_size=0.2, random_state=1)
    validate_filenames, test_filenames = train_test_split(test_validate_filenames, test_size=0.5, random_state=1)

    print(f"   Train examples: {len(train_filenames)}")
    print(f"Validate examples: {len(validate_filenames)}")
    print(f"    Test examples: {len(test_filenames)}")

    train = train_generator(train_filenames, 2, aug_dict)

    def gen_test_images():
        for filename in test_filenames["image"]:
            yield load_resize_reshape(filename, (256, 256))

    def gen_test_masks():
        for filename in test_filenames["mask"]:
            mask = load_resize_reshape(filename, (256, 256))
            mask[mask > 0.5] = 1
            mask[mask <= 0.5] = 0
            yield mask

    def gen_validate_images():
        for filename in validate_filenames["image"]:
            yield load_resize_reshape(filename, (256, 256))

    def gen_validate_masks():
        for filename in validate_filenames["mask"]:
            mask = load_resize_reshape(filename, (256, 256))
            mask[mask > 0.5] = 1
            mask[mask <= 0.5] = 0
            yield mask

    test_images = tf.data.Dataset.from_generator(gen_test_images, output_types=tf.float32)
    test_masks = tf.data.Dataset.from_generator(gen_test_masks, output_types=tf.float32)
    test = tf.data.Dataset.zip((test_images, test_masks))

    validate_images = tf.data.Dataset.from_generator(gen_validate_images, output_types=tf.float32)
    validate_masks = tf.data.Dataset.from_generator(gen_validate_masks, output_types=tf.float32)
    validate = tf.data.Dataset.zip((validate_images, validate_masks))
    return train, validate, test


def train_generator(train_df, batch_size, aug_dict, image_color_mode="grayscale", mask_color_mode="grayscale",
                    image_save_prefix="image", mask_save_prefix="mask", save_to_dir=None, target_size=(256, 256),
                    seed=1):
    image_datagen = tf.keras.preprocessing.image.ImageDataGenerator(**aug_dict)
    mask_datagen = tf.keras.preprocessing.image.ImageDataGenerator(**aug_dict)
    image_generator = image_datagen.flow_from_dataframe(
        train_df,
        x_col="image",
        class_mode=None,
        color_mode=image_color_mode,
        target_size=target_size,
        batch_size=batch_size,
        save_to_dir=save_to_dir,
        save_prefix=image_save_prefix,
        seed=seed)
    mask_generator = mask_datagen.flow_from_dataframe(
        train_df,
        x_col="mask",
        class_mode=None,
        color_mode=mask_color_mode,
        target_size=target_size,
        batch_size=batch_size,
        save_to_dir=save_to_dir,
        save_prefix=mask_save_prefix,
        seed=seed)
    for img, mask in zip(image_generator, mask_generator):
        img, mask = adjust_data(img, mask)
        yield img, mask


def load_resize_reshape(filename, target_size=(256, 256)):
    img = skimage.io.imread(filename, as_gray=True)
    img = skimage.transform.resize(img, target_size)
    img = img[np.newaxis, :, :, np.newaxis]
    d_min = img.min()
    d_max = img.max()
    img -= d_min
    img /= d_max - d_min
    return img


def save_result(save_path, npyfile):
    for i, item in enumerate(npyfile):
        img = item[:, :, 0]
        skimage.io.imsave(os.path.join(save_path, "%d_predict.png" % i), img)
