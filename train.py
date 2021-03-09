from functools import partial
import argparse
import numpy as np

import os
import datetime
import tqdm

import torch
from torch.utils.data import DataLoader
from torchvision.transforms import Compose, RandomVerticalFlip, RandomHorizontalFlip

from dcgan import DCGAN, Discriminator, Generator
from utils import square, resize, AstroDataset, get_manifold_image, logging
import warnings
warnings.filterwarnings('ignore')

arg_parse = argparse.ArgumentParser()

arg_parse.add_argument('--n_epoch', type=int, help="Number of epochs", default=100)
arg_parse.add_argument('--gen_lr', type=float, help='Generator learning rate. Default 1e-3', default=1e-3)
arg_parse.add_argument('--dis_lr', type=float, help='Discriminator learning rate. Default 2e-4', default=2e-4)
arg_parse.add_argument('--batch_size', type=int, help='Batch size', default=32)
arg_parse.add_argument('--device', type=str, help='device. Default cpu', default='cpu')
arg_parse.add_argument('--z_dim', type=int, help='Latent dimension', default=3)
arg_parse.add_argument('--ngf', type=int, help='Number of generator features', default=64)
arg_parse.add_argument('--ndf', type=int, help='Number of Discriminator features', default=64)
arg_parse.add_argument('--im_size', type=int, help='Image size', default=64)
arg_parse.add_argument('--data_dir', type=str, help="Path to data directory")
arg_parse.add_argument('--checkpoints_dir', type=str, help="Path to checkpoints directory")


args = arg_parse.parse_args()

transform = Compose([square,
                     partial(resize, size=(args.im_size, args.im_size)),
                     RandomHorizontalFlip(),
                     RandomVerticalFlip()
                     ])

dataset = AstroDataset(args.data_dir, transform=transform)
data_loader = DataLoader(dataset, args.batch_size, shuffle=True, num_workers=4)

# Build DCGAN model
generator = Generator(z_dim=args.z_dim, ngf=args.ngf, n_ch=3)
discriminator = Discriminator(n_ch=3, ndf=args.ndf)

dcgan = DCGAN(generator, discriminator, args.device, args.z_dim, generator_lr=1e-3, discriminator_lr=2e-4)

# Directory for checkpoints
path_to_save = f'{args.checkpoints_dir}/hubble/{datetime.datetime.now()}'
os.makedirs(path_to_save, exist_ok=True)
os.makedirs(os.path.join(path_to_save, f'test_images'), exist_ok=True)

test_z = torch.randn(5 * 5, args.z_dim, 1, 1).to(args.device)

print("Start training...")
print(dcgan.cnt_parameters)

for epoch in range(args.n_epoch):
    dcgan.G.train()
    G_epoch_loss = []
    D_epoch_loss = []
    real_D_epoch_loss = []
    fake_D_epoch_loss = []

    for train_batch in tqdm.tqdm(data_loader):
        D_loss, (real_D_loss, fake_D_loss) = dcgan.train_dis_step(train_batch)
        G_loss = dcgan.train_gen_step(train_batch)
        while epoch > 0 and fake_D_loss < 0.1 and G_loss > 1.:
            G_loss = dcgan.train_gen_step(train_batch)

        G_epoch_loss.append(G_loss)
        D_epoch_loss.append(D_loss)
        real_D_epoch_loss.append(real_D_loss)
        fake_D_epoch_loss.append(fake_D_loss)
    if epoch % 5 == 0:
        torch.save(dcgan.G.state_dict(), os.path.join(path_to_save, f'Generator_epoch_{epoch + 1}.pth'))
        torch.save(dcgan.D.state_dict(), os.path.join(path_to_save, f'Discriminator_epoch_{epoch + 1}.pth'))

        dcgan.G.eval()
        pred_test_images = dcgan.G(test_z)
        get_manifold_image(pred_test_images, im_size=(args.im_size, args.im_size), mode='RGB').save(
            os.path.join(path_to_save, f'test_images', f'epoch_{epoch + 1}.jpg'))

    log = f"Epoch: {epoch + 1}\tTrain_gen_loss: {np.mean(G_epoch_loss)}\t" \
            f"real score: {np.mean(real_D_epoch_loss)}\tfake score: {np.mean(fake_D_epoch_loss)}"
    logging(log, path_to_save)
    print()
    print(log)
