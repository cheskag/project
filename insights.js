import { Router } from 'express';
import {
  addComment,
  createPost,
  deleteComment,
  deletePost,
  getPosts,
  toggleReaction,
} from '../controllers/communityController.js';
import { authenticateJWT } from '../middleware/authMiddleware.js';

const router = Router();

router.use(authenticateJWT);
router.get('/posts', getPosts);
router.post('/posts', createPost);
router.post('/posts/:postId/comments', addComment);
router.post('/posts/:postId/reactions', toggleReaction);
router.delete('/posts/:postId', deletePost);
router.delete('/posts/:postId/comments/:commentId', deleteComment);

export default router;

