const express = require('express');
const multer = require('multer');
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');

const app = express();
const port = 3000;

// Tell Express to serve HTML and CSS files from the "public" folder
app.use(express.static(path.join(__dirname, 'public')));

const tempDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir);

// Serve the index.html file
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// Configure Multer for video uploads (limits file size to 500MB)
const upload = multer({ dest: 'uploads/', limits: { fileSize: 500 * 1024 * 1024 } });

// The route that connects Node.js to Python
app.post('/api/transcribe', upload.single('video'), async (req, res) => {
    try {
        const { language } = req.body;
        const file = req.file;

        if (!file) return res.status(400).send('No video uploaded.');

        console.log(`Sending ${file.originalname} to Python Engine...`);

        // Prepare the payload for Python
        const form = new FormData();
        form.append('video', fs.createReadStream(file.path), file.originalname);
        form.append('language', language);

        // Call the Python FastAPI Server
        const response = await axios.post('http://localhost:8000/process-video', form, {
            headers: { ...form.getHeaders() },
            responseType: 'stream',
            maxBodyLength: Infinity,
            timeout: 300000 // 5-minute timeout for long videos
        });

        // Forward the .srt file stream back to the user's browser
        res.setHeader('Content-Disposition', `attachment; filename="transcript.srt"`);
        res.setHeader('Content-Type', 'application/x-subrip');
        response.data.pipe(res);

        // Delete the temporary file from the Node server after sending
        fs.unlinkSync(file.path);

    } catch (error) {
        console.error('Python API Error:', error.message);
        res.status(500).send('Failed to process video.');
    }
});

app.listen(port, () => console.log(`Frontend running! Open http://localhost:${port} in your browser`));