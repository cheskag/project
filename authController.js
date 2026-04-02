import mongoose from 'mongoose';

const collectionName = process.env.MONGO_COLLECTION || 'admin';

const adminSchema = new mongoose.Schema(
  {
    data: { type: Object, required: true },
    uploadedAt: { type: Date, default: Date.now },
  },
  {
    collection: collectionName,
  }
);

const AdminEntry = mongoose.models.AdminEntry || mongoose.model('AdminEntry', adminSchema);

export const uploadJson = async (req, res) => {
  try {
    if (!req.body || !req.body.data) {
      return res.status(400).json({ error: 'No data provided' });
    }

    const doc = new AdminEntry({ data: req.body.data });
    await doc.save();
    res.json({ message: 'JSON data saved', id: doc._id });
  } catch (err) {
    console.error('[Admin Upload] Failed to save JSON data:', err);
    res.status(500).json({ error: 'Failed to save JSON data' });
  }
}; 