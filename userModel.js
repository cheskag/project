import mongoose from 'mongoose';

const { Schema } = mongoose;

const CommentSchema = new Schema(
  {
    commentId: {
      type: String,
      default: () => new mongoose.Types.ObjectId().toString(),
    },
    userId: {
      type: String,
      required: true,
      trim: true,
    },
    displayName: {
      type: String,
      required: true,
      trim: true,
    },
    content: {
      type: String,
      required: true,
      trim: true,
    },
    createdAt: {
      type: Date,
      default: Date.now,
    },
  },
  { _id: false },
);

const ReactionSchema = new Schema(
  {
    userId: {
      type: String,
      required: true,
      trim: true,
    },
    displayName: {
      type: String,
      default: '',
      trim: true,
    },
    createdAt: {
      type: Date,
      default: Date.now,
    },
  },
  { _id: false },
);

const CommunityPostSchema = new Schema(
  {
    authorId: {
      type: String,
      default: 'legacy',
      trim: true,
    },
    displayName: {
      type: String,
      required: true,
      trim: true,
    },
    content: {
      type: String,
      required: true,
      trim: true,
    },
    comments: {
      type: [CommentSchema],
      default: [],
    },
    reactions: {
      type: [ReactionSchema],
      default: [],
    },
    createdAt: {
      type: Date,
      default: Date.now,
    },
    updatedAt: {
      type: Date,
      default: Date.now,
    },
  },
  {
    timestamps: false,
  },
);

CommunityPostSchema.index({ createdAt: -1 });

const CommunityPost =
  mongoose.models.CommunityPost || mongoose.model('CommunityPost', CommunityPostSchema);

export default CommunityPost;

