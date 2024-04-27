import torch; torch.manual_seed(0)
import torch.nn as nn
import torch.nn.functional as F
import torch.utils
import torch.distributions
import torchvision
import numpy as np
import matplotlib.pyplot as plt


device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(device)



class Encoder(nn.Module):
    def __init__(self, latent_dims):
        super(Encoder, self).__init__()
        self.linear1 = nn.Linear(784, 512)
        self.linear2 = nn.Linear(512, latent_dims)

    def forward(self, x):
        x = torch.flatten(x, start_dim=1)
        x = F.relu(self.linear1(x))
        return self.linear2(x)


class Decoder(nn.Module):
    def __init__(self, latent_dims):
        super(Decoder, self).__init__()
        self.linear1 = nn.Linear(latent_dims, 512)
        self.linear2 = nn.Linear(512, 784)

    def forward(self, z):
        z = F.relu(self.linear1(z))
        z = torch.sigmoid(self.linear2(z))
        return z.reshape((-1, 1, 28, 28))


class Autoencoder(nn.Module):
    def __init__(self, latent_dims):
        super(Autoencoder, self).__init__()
        self.encoder = Encoder(latent_dims)
        self.decoder = Decoder(latent_dims)

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z)


def train(autoencoder, data, epochs, batch_size):
    opt = torch.optim.Adam(autoencoder.parameters())
    for epoch in range(epochs):

        total_loss = 0
        for x, y in data:

            x = x.to(device) # GPU

            opt.zero_grad()

            x_hat = autoencoder(x)
            loss = ((x - x_hat)**2).sum()
            total_loss += loss.item()

            loss.backward()
            opt.step()

        print("\tEpoch", epoch + 1, "complete!", "\tAverage Loss: ", total_loss/batch_size)
    return autoencoder


latent_dims = 2
batch_size = 128
epochs = 3
autoencoder = Autoencoder(latent_dims).to(device) # GPU

data = torch.utils.data.DataLoader(
        torchvision.datasets.MNIST('./mnist_dataset',
               transform=torchvision.transforms.ToTensor(),
               download=True),
        batch_size=batch_size,
        shuffle=True)

autoencoder = train(autoencoder, data, epochs, batch_size)

def plot_latent(autoencoder, data, num_batches=10):
    for i, (x, y) in enumerate(data):
        z = autoencoder.encoder(x.to(device))
        z = z.to('cpu').detach().numpy()
        plt.scatter(z[:, 0], z[:, 1], c=y, cmap='tab10')
        if i > num_batches:
            plt.colorbar()
            break

save_path = "./result/ae_mnist.png"

plot_latent(autoencoder, data)
plt.savefig(save_path)