import os
import json
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import numpy as np

# Set random seeds for exact reproducibility
torch.manual_seed(42)
np.random.seed(42)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "sequences_data.npz")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)
MODEL_SAVE_PATH = os.path.join(MODELS_DIR, "best_lstm_anomaly_detector.pt")
HISTORY_SAVE_PATH = os.path.join(MODELS_DIR, "training_history.json")

print("=" * 70)
print(" STEP 8 & 9: LSTM MODEL ARCHITECTURE & TRAINING PIPELINE ")
print("=" * 70)

# 1. Load sequence tensors
print("\n[1] Loading Preprocessed 3D Tensors...")
data = np.load(DATA_PATH)
X_train = torch.tensor(data["X_train"], dtype=torch.float32)
y_train = torch.tensor(data["y_train"], dtype=torch.float32)
X_val = torch.tensor(data["X_val"], dtype=torch.float32)
y_val = torch.tensor(data["y_val"], dtype=torch.float32)
X_test = torch.tensor(data["X_test"], dtype=torch.float32)
y_test = torch.tensor(data["y_test"], dtype=torch.float32)

print(f"   - X_train shape: {X_train.shape}")
print(f"   - X_val shape:   {X_val.shape}")
print(f"   - X_test shape:  {X_test.shape}")

BATCH_SIZE = 64
train_loader = DataLoader(TensorDataset(X_train, X_train), batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(TensorDataset(X_val, X_val), batch_size=BATCH_SIZE, shuffle=False)
test_loader = DataLoader(TensorDataset(X_test, y_test), batch_size=BATCH_SIZE, shuffle=False)

# 2. Define LSTM Autoencoder Architecture
class LSTMAutoencoder(nn.Module):
    def __init__(self, seq_len=15, n_features=30, hidden_dim=64, latent_dim=32):
        super(LSTMAutoencoder, self).__init__()
        self.seq_len = seq_len
        self.n_features = n_features
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        
        # Encoder
        self.encoder_lstm1 = nn.LSTM(input_size=n_features, hidden_size=hidden_dim, batch_first=True)
        self.encoder_dropout = nn.Dropout(0.2)
        self.encoder_lstm2 = nn.LSTM(input_size=hidden_dim, hidden_size=latent_dim, batch_first=True)
        
        # Decoder
        self.decoder_lstm1 = nn.LSTM(input_size=latent_dim, hidden_size=hidden_dim, batch_first=True)
        self.decoder_dropout = nn.Dropout(0.2)
        self.decoder_dense = nn.Linear(hidden_dim, n_features)

    def forward(self, x):
        # Encoder: x -> (batch, 15, 30)
        out, _ = self.encoder_lstm1(x)
        out = self.encoder_dropout(out)
        _, (hn, _) = self.encoder_lstm2(out) # hn: (1, batch, latent_dim)
        
        # Repeat latent vector across time steps: (batch, 15, latent_dim)
        latent_repeated = hn.permute(1, 0, 2).repeat(1, self.seq_len, 1)
        
        # Decoder
        dec_out, _ = self.decoder_lstm1(latent_repeated)
        dec_out = self.decoder_dropout(dec_out)
        reconstruction = self.decoder_dense(dec_out) # (batch, 15, 30)
        
        return reconstruction

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"\n[2] Initializing LSTM Architecture on device: {device}")
model = LSTMAutoencoder(seq_len=15, n_features=30, hidden_dim=64, latent_dim=32).to(device)
print(model)

# 3. Training Configuration
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3)

EPOCHS = 25
PATIENCE = 7
best_val_loss = float('inf')
patience_counter = 0

train_losses = []
val_losses = []

print("\n[3] Commencing LSTM Model Training:")
print("-" * 70)

for epoch in range(1, EPOCHS + 1):
    model.train()
    total_train_loss = 0.0
    for batch_x, _ in train_loader:
        batch_x = batch_x.to(device)
        optimizer.zero_grad()
        recon = model(batch_x)
        loss = criterion(recon, batch_x)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        total_train_loss += loss.item() * len(batch_x)
        
    avg_train_loss = total_train_loss / len(X_train)
    train_losses.append(avg_train_loss)
    
    # Validation phase
    model.eval()
    total_val_loss = 0.0
    with torch.no_grad():
        for batch_val, _ in val_loader:
            batch_val = batch_val.to(device)
            recon_val = model(batch_val)
            val_loss = criterion(recon_val, batch_val)
            total_val_loss += val_loss.item() * len(batch_val)
            
    avg_val_loss = total_val_loss / len(X_val)
    val_losses.append(avg_val_loss)
    scheduler.step(avg_val_loss)
    
    current_lr = optimizer.param_groups[0]['lr']
    print(f"Epoch [{epoch:02d}/{EPOCHS:02d}] | Train Loss: {avg_train_loss:.6f} | Val Loss: {avg_val_loss:.6f} | LR: {current_lr:.6f}")
    
    # Early Stopping & Best Model Checkpointing
    if avg_val_loss < best_val_loss:
        best_val_loss = avg_val_loss
        patience_counter = 0
        torch.save(model.state_dict(), MODEL_SAVE_PATH)
    else:
        patience_counter += 1
        if patience_counter >= PATIENCE:
            print(f"\n[!] Early stopping triggered at epoch {epoch}. Restoring best checkpoint (Val Loss: {best_val_loss:.6f}).")
            break

# Save Training History
with open(HISTORY_SAVE_PATH, "w") as f:
    json.dump({
        "train_losses": train_losses,
        "val_losses": val_losses,
        "best_val_loss": best_val_loss,
        "epochs_trained": len(train_losses)
    }, f, indent=2)

print(f"\n[4] Best model weights saved to: {MODEL_SAVE_PATH}")
print(f"[5] Training history saved to:   {HISTORY_SAVE_PATH}")

print("\n" + "=" * 70)
print(" STEP 8 & 9 EXECUTION COMPLETE ")
print("=" * 70)
