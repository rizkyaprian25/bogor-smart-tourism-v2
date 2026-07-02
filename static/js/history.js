/**
 * History Page — Delete Functionality
 */

let deleteHistoryId = null;

function deleteHistory(historyId) {
  if (!historyId || historyId === 'None' || historyId === 'null') {
    showToast('ID history tidak valid', true);
    return;
  }
  
  deleteHistoryId = historyId;
  console.log('deleteHistoryId set to:', deleteHistoryId);
  document.getElementById('deleteOverlay').style.display = 'flex';
}

function hideDeleteConfirm() {
  deleteHistoryId = null;
  document.getElementById('deleteOverlay').style.display = 'none';
}

async function executeDelete() {
  if (!deleteHistoryId || deleteHistoryId === 'null' || deleteHistoryId === 'None') {
    hideDeleteConfirm();
    showToast('ID history tidak ditemukan', true);
    return;
  }

  // Simpan ID ke variabel lokal SEBELUM hideDeleteConfirm() me-reset ke null
  const idToDelete = deleteHistoryId;
  hideDeleteConfirm();
  showLoading(true, 'Menghapus...');

  try {
    const response = await fetch(`/api/history/${idToDelete}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json();

    if (data.status === 'ok') {
      const card = document.querySelector(`.history-card[data-history-id="${idToDelete}"]`);
      if (card) {
        card.style.transition = 'opacity 0.3s';
        card.style.opacity = '0';
        setTimeout(() => card.remove(), 300);
      }
      showToast('Riwayat berhasil dihapus', false);
      setTimeout(() => {
        if (!document.querySelector('.history-card')) window.location.reload();
      }, 500);
    } else {
      showToast(data.error || 'Gagal menghapus riwayat', true);
    }
  } catch (error) {
    console.error('Delete error:', error);
    showToast('Terjadi kesalahan saat menghapus', true);
  } finally {
    showLoading(false);
  }
}

// Close modal on outside click
document.addEventListener('click', function(e) {
  if (e.target.id === 'deleteOverlay') {
    hideDeleteConfirm();
  }
});