import mongoose from 'mongoose';
import CommunityPost from '../models/communityPostModel.js';

const sanitizeText = (value = '') => value.toString().trim().slice(0, 1000);

const buildPostResponse = (postDoc, viewerUserId) => {
  if (!postDoc) return null;
  const post = postDoc.toObject ? postDoc.toObject() : postDoc;
  const reactions = Array.isArray(post.reactions) ? post.reactions : [];
  const comments = Array.isArray(post.comments) ? post.comments : [];

  return {
    id: post._id.toString(),
    displayName: post.displayName || 'Member',
    authorId: post.authorId,
    content: post.content,
    createdAt: post.createdAt,
    updatedAt: post.updatedAt,
    reactionCount: reactions.length,
    viewerHasReacted: viewerUserId
      ? reactions.some((reaction) => (reaction.userId || reaction.sessionId) === viewerUserId)
      : false,
    comments: comments
      .slice()
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
      .map((comment) => ({
        commentId: comment.commentId,
        userId: comment.userId,
        displayName: comment.displayName || 'Member',
        content: comment.content,
        createdAt: comment.createdAt,
      })),
  };
};

const getUserIdentity = (req) => {
  const user = req.user || {};
  const userId = (user.id || user.email || '').toString().trim();
  if (!userId) {
    const err = new Error('Authentication required');
    err.statusCode = 401;
    throw err;
  }
  const displayNameRaw = user.fullname || user.email || 'Member';
  const displayName = sanitizeText(displayNameRaw).slice(0, 120) || 'Member';
  return { userId, displayName };
};

export const getPosts = async (req, res) => {
  try {
    const { userId } = getUserIdentity(req);
    const posts = await CommunityPost.find().sort({ createdAt: -1 }).lean();
    const payload = posts.map((post) => buildPostResponse(post, userId));
    res.json({ posts: payload });
  } catch (error) {
    console.error('[Community] Failed to load posts:', error);
    res.status(500).json({ error: 'Failed to fetch community posts' });
  }
};

export const createPost = async (req, res) => {
  try {
    const { userId, displayName } = getUserIdentity(req);
    const content = sanitizeText(req.body?.content);

    if (!content) {
      return res.status(400).json({ error: 'Content is required.' });
    }

    const newPost = await CommunityPost.create({
      authorId: userId,
      displayName,
      content,
      comments: [],
      reactions: [],
    });

    const refreshed = await CommunityPost.findById(newPost._id);
    res.status(201).json({ post: buildPostResponse(refreshed, userId) });
  } catch (error) {
    const status = error.statusCode || 500;
    console.error('[Community] Failed to create post:', error);
    res.status(status).json({ error: error.message || 'Failed to create post.' });
  }
};

export const addComment = async (req, res) => {
  try {
    const { userId, displayName } = getUserIdentity(req);
    const { postId } = req.params;
    if (!mongoose.Types.ObjectId.isValid(postId)) {
      return res.status(400).json({ error: 'Invalid post identifier.' });
    }

    const content = sanitizeText(req.body?.content);
    if (!content) {
      return res.status(400).json({ error: 'Content is required.' });
    }

    const comment = {
      commentId: new mongoose.Types.ObjectId().toString(),
      userId,
      displayName,
      content,
      createdAt: new Date(),
    };

    const updatedPost = await CommunityPost.findByIdAndUpdate(
      postId,
      {
        $push: { comments: { $each: [comment], $position: 0 } },
        $set: { updatedAt: new Date() },
      },
      { new: true },
    );

    if (!updatedPost) {
      return res.status(404).json({ error: 'Post not found.' });
    }

    res.status(201).json({ post: buildPostResponse(updatedPost, userId) });
  } catch (error) {
    const status = error.statusCode || 500;
    console.error('[Community] Failed to add comment:', error);
    res.status(status).json({ error: error.message || 'Failed to add comment.' });
  }
};

export const toggleReaction = async (req, res) => {
  try {
    const { userId, displayName } = getUserIdentity(req);
    const { postId } = req.params;
    if (!mongoose.Types.ObjectId.isValid(postId)) {
      return res.status(400).json({ error: 'Invalid post identifier.' });
    }

    const post = await CommunityPost.findById(postId);
    if (!post) {
      return res.status(404).json({ error: 'Post not found.' });
    }

    const existingIndex = post.reactions.findIndex(
      (reaction) => (reaction.userId || reaction.sessionId) === userId,
    );

    if (existingIndex >= 0) {
      post.reactions.splice(existingIndex, 1);
    } else {
      post.reactions.push({
        userId,
        displayName,
        createdAt: new Date(),
      });
    }

    post.updatedAt = new Date();
    await post.save();

    const refreshed = await CommunityPost.findById(postId);
    res.json({ post: buildPostResponse(refreshed, userId) });
  } catch (error) {
    const status = error.statusCode || 500;
    console.error('[Community] Failed to toggle reaction:', error);
    res.status(status).json({ error: error.message || 'Failed to toggle reaction.' });
  }
};

export const deletePost = async (req, res) => {
  try {
    const { userId } = getUserIdentity(req);
    const { postId } = req.params;
    if (!mongoose.Types.ObjectId.isValid(postId)) {
      return res.status(400).json({ error: 'Invalid post identifier.' });
    }

    const post = await CommunityPost.findById(postId);
    if (!post) {
      return res.status(404).json({ error: 'Post not found.' });
    }

    const isOwner = (post.authorId || post.userId) === userId || userId === 'admin';
    if (!isOwner) {
      return res.status(403).json({ error: 'You do not have permission to delete this post.' });
    }

    await CommunityPost.findByIdAndDelete(postId);
    res.json({ success: true });
  } catch (error) {
    const status = error.statusCode || 500;
    console.error('[Community] Failed to delete post:', error);
    res.status(status).json({ error: error.message || 'Failed to delete post.' });
  }
};

export const deleteComment = async (req, res) => {
  try {
    const { userId } = getUserIdentity(req);
    const { postId, commentId } = req.params;
    if (!mongoose.Types.ObjectId.isValid(postId) || !commentId) {
      return res.status(400).json({ error: 'Invalid identifiers.' });
    }

    const post = await CommunityPost.findById(postId);
    if (!post) {
      return res.status(404).json({ error: 'Post not found.' });
    }

    const commentIndex = post.comments.findIndex((comment) => comment.commentId === commentId);
    if (commentIndex === -1) {
      return res.status(404).json({ error: 'Comment not found.' });
    }

    const target = post.comments[commentIndex];
    const isOwner =
      target.userId === userId ||
      (post.authorId || post.userId) === userId ||
      userId === 'admin';
    if (!isOwner) {
      return res.status(403).json({ error: 'You do not have permission to delete this comment.' });
    }

    post.comments.splice(commentIndex, 1);
    post.updatedAt = new Date();
    await post.save();

    const refreshed = await CommunityPost.findById(postId);
    res.json({ post: buildPostResponse(refreshed, userId) });
  } catch (error) {
    const status = error.statusCode || 500;
    console.error('[Community] Failed to delete comment:', error);
    res.status(status).json({ error: error.message || 'Failed to delete comment.' });
  }
};


