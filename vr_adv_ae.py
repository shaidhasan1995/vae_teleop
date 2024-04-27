import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.datasets as dsets
import torchvision.transforms as transforms
from torch.autograd import Variable
import os
import matplotlib.pyplot as plt
from loader import *
from models import *
from sklearn.manifold import TSNE

mnist_path = '/scratch/qmz9mg/vae/data'
device = 'cuda' if torch.cuda.is_available() else 'cpu'


def to_np(x):
    return x.data.cpu().numpy()

def to_var(x):
    if torch.cuda.is_available():
        x = x.cuda()
    return Variable(x)

#Encoder
class Q_net(nn.Module):  
    def __init__(self,X_dim, hidden_size,z_dim):
        super(Q_net, self).__init__()
        self.lin1 = nn.Linear(X_dim, hidden_size*8)
        self.lin2 = nn.Linear(hidden_size*8, hidden_size*2)
        self.lin3gauss = nn.Linear(hidden_size*2, z_dim)
    def forward(self, x):
        x = F.dropout(self.lin1(x), p=0.25, training=self.training)
        x = F.relu(x)
        x = F.dropout(self.lin2(x), p=0.25, training=self.training)
        x = F.relu(x)
        xgauss = self.lin3gauss(x)
        return xgauss

# Decoder
class P_net(nn.Module):  
    def __init__(self,X_dim,hidden_size,z_dim):
        super(P_net, self).__init__()
        self.lin1 = nn.Linear(z_dim, hidden_size*2)
        self.lin2 = nn.Linear(hidden_size*2, hidden_size*8)
        self.lin3 = nn.Linear(hidden_size*8, X_dim)
    def forward(self, x):
        x = F.dropout(self.lin1(x), p=0.25, training=self.training)
        x = F.relu(x)
        x = F.dropout(self.lin2(x), p=0.25, training=self.training)
        x = self.lin3(x)
        return F.sigmoid(x)

# Discriminator
class D_net_gauss(nn.Module):  
    def __init__(self,hidden_size,z_dim):
        super(D_net_gauss, self).__init__()
        self.lin1 = nn.Linear(z_dim, hidden_size)
        self.lin2 = nn.Linear(hidden_size, hidden_size)
        self.lin3 = nn.Linear(hidden_size, 1)
    def forward(self, x):
        x = F.dropout(self.lin1(x), p=0.2, training=self.training)
        x = F.relu(x)
        x = F.dropout(self.lin2(x), p=0.2, training=self.training)
        x = F.relu(x)
        return F.sigmoid(self.lin3(x))  


input_size = 8
hidden_size = 64
num_layers = 2
latent_dim = 12
batch_size = 10
# seq_len = 1100
chunk_size = 100
z_red_dims = latent_dim
seq_len = chunk_size

Q = Q_net(seq_len*input_size,hidden_size,latent_dim).cuda()
P = P_net(seq_len*input_size,hidden_size,latent_dim).cuda()
D_gauss = D_net_gauss(hidden_size,latent_dim).cuda()

print(Q)
print(P)
print(D_gauss)


dataset = VR_input_Dataset()
chunked_dataset = ChunkedDataset(original_dataset = VR_input_Dataset(), chunk_size=chunk_size)
data_loader = DataLoader(chunked_dataset, batch_size=10, shuffle=True)

####################### Dataloader and Model Test #####################

dataiter = iter(data_loader)
X, Y = next(dataiter)
print("X.shape(original):", X.shape)

X, Y = to_var(X.view(X.size(0), -1)), to_var(Y)
print("X.shape:",X.shape)
print("Y.shape:",Y.shape)

latent_z = Q(X)
print("latent_z.shape:",latent_z.shape)   
X_hat = P(latent_z)
print("X_hat.shape:",X_hat.shape) 
z_fake_gauss = Q(X)
D_fake_gauss = D_gauss(z_fake_gauss)
print("D_fake_gauss.shape:",D_fake_gauss.shape)

####################### *************************** #####################

# Set learning rates
gen_lr = 0.001
reg_lr = 0.001
EPS = 1e-15
adversarial_loss = nn.BCELoss()
reconstruction_loss = nn.MSELoss()

optim_Q_enc = torch.optim.Adam(Q.parameters(), lr=gen_lr)
optim_P = torch.optim.Adam(P.parameters(), lr=gen_lr)
optim_Q_gen = torch.optim.Adam(Q.parameters(), lr=reg_lr)
optim_D = torch.optim.Adam(D_gauss.parameters(), lr=reg_lr)


epochs = 30
Reconstruction_loss = []
Discriminator_loss = []
Generator_loss = []

for epoch in range(epochs):

    for batch_idx, (X, Y) in enumerate(data_loader):

        X, Y = to_var(X.view(X.size(0), -1)), to_var(Y)
        # print("X.shape:",X.shape)
        # print("Y.shape:",Y.shape)

        P.zero_grad()
        Q.zero_grad()
        D_gauss.zero_grad()

        # Reconstruction Loss and Optimization of Q and P
        latent_z = Q(X)   
        X_hat = P(latent_z)
        recon_loss = reconstruction_loss(X_hat+EPS,X+EPS)      
        recon_loss.backward()
        optim_P.step()
        optim_Q_enc.step()
        # print(f"Epoch {epoch+1}: recon_loss: {recon_loss.item():.8f}")
         
        # Adversarial Loss and Optimization of D
        Q.eval()
        real_gauss_label = torch.ones((X.shape[0], 1), requires_grad=False).cuda()
        z_real_gauss = (torch.randn(X.size()[0], z_red_dims) * 5.).cuda()
        D_real_gauss = D_gauss(z_real_gauss)
        
        fake_gauss_label = torch.zeros((X.shape[0], 1), requires_grad=False).cuda()
        z_fake_gauss = Q(X)
        D_fake_gauss = D_gauss(z_fake_gauss)

        real_loss = adversarial_loss(D_real_gauss, real_gauss_label)
        fake_loss = adversarial_loss(D_fake_gauss, fake_gauss_label)
        D_loss = 0.5*(real_loss + fake_loss)
        # D_loss = -torch.mean(torch.log(D_real_gauss + EPS) + torch.log(1 - D_fake_gauss + EPS))
        D_loss.backward()
        optim_D.step()
        # print(f"Epoch {epoch+1}: D_loss: {D_loss.item():.8f}")
        

        # Adversarial Loss and Optimization of Q
        Q.train()
        z_fake_gauss = Q(X)
        D_fake_gauss = D_gauss(z_fake_gauss)
        # G_loss = -torch.mean(torch.log(D_fake_gauss)+EPS)
        G_loss = adversarial_loss(D_fake_gauss, real_gauss_label)
        G_loss.backward()
        optim_Q_gen.step()
        # print(f"Epoch {epoch+1}: G_loss: {G_loss.item():.8f}")
        
    Reconstruction_loss.append(recon_loss.item())
    Discriminator_loss.append(D_loss.item())  
    Generator_loss.append(G_loss.item())  
    print(f"Epoch {epoch+1}: recon_loss: {recon_loss.item():.8f}, D_loss: {D_loss.item():.8f}, G_loss: {G_loss.item():.8f}")

def plot_adver_ae_latent_2D(model, train_loader, save_path):

    all_z = []
    all_y = []
    model.eval()
    for i, (x, y) in enumerate(train_loader):
        x, y = to_var(x.view(x.size(0), -1)), to_var(y)
        z = model(x.to(device))
        z = z.to('cpu').detach().numpy()
        y = y.to('cpu').detach().numpy()
        all_z.append(z)
        all_y.append(y)

    all_z = np.concatenate(all_z, axis=0)
    all_y = np.concatenate(all_y, axis=0)

    tsne = TSNE(n_components=2, random_state=0, perplexity=10)
    all_z_reduced = tsne.fit_transform(all_z)
    
    all_y = all_y.reshape(-1)

    plt.figure(figsize=(8, 8))
    for i in range(2):
        plt.scatter(all_z_reduced[all_y == i, 0], all_z_reduced[all_y == i, 1], label=str(i))

    plt.legend()
    plt.xticks([])
    plt.yticks([])

    plt.xlabel('t-SNE feature 1')
    plt.ylabel('t-SNE feature 2')
    plt.title("t-SNE visualization") 
    plt.show()
    plt.savefig(save_path)

def plot_losses_subplots_and_save(Reconstruction_loss, Discriminator_loss, Generator_loss, save_path):
    epochs = range(len(Reconstruction_loss))

    fig, axs = plt.subplots(3, 1, figsize=(10, 15))

    axs[0].plot(epochs, Reconstruction_loss, label='Reconstruction Loss', color='blue')
    axs[0].set_title('Reconstruction Loss')
    axs[0].set_xlabel('Epoch')
    axs[0].set_ylabel('Loss')
    axs[0].legend()
    axs[0].grid(True)

    axs[1].plot(epochs, Discriminator_loss, label='Discriminator Loss', color='orange')
    axs[1].set_title('Discriminator Loss')
    axs[1].set_xlabel('Epoch')
    axs[1].set_ylabel('Loss')
    axs[1].legend()
    axs[1].grid(True)

    axs[2].plot(epochs, Generator_loss, label='Generator Loss', color='green')
    axs[2].set_title('Generator Loss')
    axs[2].set_xlabel('Epoch')
    axs[2].set_ylabel('Loss')
    axs[2].legend()
    axs[2].grid(True)

    plt.tight_layout()
    plt.savefig(save_path)  # Save the plot
    plt.close()  # Close the plot to avoid displaying it
    
    print(f"Plot saved at: {save_path}")

save_path = "/scratch/qmz9mg/vae/results/advers_ae_loss_plot.png"
tsne_path = "/scratch/qmz9mg/vae/results/advers_ae_tsne.png"
plot_losses_subplots_and_save(Reconstruction_loss, Discriminator_loss, Generator_loss, save_path)
data_loade_eval = DataLoader(chunked_dataset, batch_size=1, shuffle=True)
plot_adver_ae_latent_2D(Q, data_loade_eval, save_path = tsne_path)