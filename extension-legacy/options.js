document.addEventListener('DOMContentLoaded', () => {
    const requestBtn = document.getElementById('request-btn');
    const statusDiv = document.getElementById('status');

    requestBtn.addEventListener('click', async () => {
        try {
            statusDiv.textContent = 'Meminta izin...';
            statusDiv.className = '';
            
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // If successful, stop all tracks immediately to release the microphone
            stream.getTracks().forEach(track => track.stop());
            
            statusDiv.textContent = '✅ Sukses! Izin mikrofon telah diberikan. Anda dapat menutup halaman ini dan kembali ke Ekstensi Anda.';
            statusDiv.className = 'success';
            requestBtn.style.display = 'none';

            // Optional: Auto close the tab after 3 seconds
            setTimeout(() => {
                window.close();
            }, 3000);
            
        } catch (err) {
            console.error('Microphone access error:', err);
            statusDiv.textContent = '❌ Gagal: ' + err.message + '. Pastikan Anda mengklik "Allow" pada peramban Anda.';
            statusDiv.className = 'error';
        }
    });
});
