# OXYCODE AI BOT - Deployment Guide

## 📋 Overview

This guide covers deploying the OXYCODE AI BOT to:
1. **VPS** (Ubuntu 22.04) using PM2
2. **Vercel** (Serverless)

---

## 🚀 VPS Deployment

### Prerequisites

- VPS with Ubuntu 22.04
- SSH access (root user)
- Node.js 20+ installed
- PM2 installed

### Step 1: Connect to VPS

```bash
ssh root@YOUR_VPS_IP
```

Password: `$VPS_PASSWORD` (use SSH key auth)

### Step 2: Install Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# Install PM2
npm install -g pm2
```

### Step 3: Clone Repository

```bash
cd /opt
git clone https://github.com/your-username/oxycode-bot.git
cd oxycode-bot
```

### Step 4: Configure Environment

```bash
# Create .env file
nano .env
```

Add your environment variables:

```env
OPENAI_API_KEY=your_openai_api_key
CLOUDFLARE_API_TOKEN=your_cf_token
CLOUDFLARE_ACCOUNT_ID=your_cf_account_id
DATABASE_URL=your_database_url
JWT_SECRET=your_jwt_secret
```

### Step 5: Install & Build

```bash
# Install dependencies
npm install

# Build the project
npm run build
```

### Step 6: Start with PM2

```bash
# Start the bot
pm2 start npm --name "oxycode-bot" -- start

# Save process list
pm2 save

# Setup startup
pm2 startup
```

### Step 7: Verify Deployment

```bash
# Check status
pm2 status

# View logs
pm2 logs oxycode-bot

# Monitor
pm2 monit
```

---

## 🌐 Vercel Deployment

### Prerequisites

- Vercel account
- Vercel CLI installed
- Git repository

### Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

### Step 2: Login to Vercel

```bash
vercel login
```

### Step 3: Configure Project

```bash
# Initialize Vercel
vercel

# Follow prompts
# - Set up for existing project? Yes
# - Which framework? Other
# - Build command? npm run build
# - Output directory? dist
```

### Step 4: Set Environment Variables

```bash
vercel env add OPENAI_API_KEY
vercel env add CLOUDFLARE_API_TOKEN
vercel env add CLOUDFLARE_ACCOUNT_ID
vercel env add DATABASE_URL
vercel env add JWT_SECRET
```

### Step 5: Deploy

```bash
# Deploy to production
vercel --prod

# Or deploy preview
vercel
```

### Step 6: Configure Domain (Optional)

```bash
# Add custom domain
vercel domains add yourdomain.com
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for AI features | ✅ |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token | ✅ |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID | ✅ |
| `DATABASE_URL` | PostgreSQL database URL | ✅ |
| `JWT_SECRET` | JWT secret for authentication | ✅ |

### Cloudflare Workers (for VPS)

If using Cloudflare Workers on VPS:

```bash
# Install Wrangler
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Deploy worker
wrangler deploy
```

---

## 📊 Monitoring

### VPS Monitoring

```bash
# Real-time monitoring
pm2 monit

# View logs
pm2 logs oxycode-bot

# Check status
pm2 status

# Restart
pm2 restart oxycode-bot

# Stop
pm2 stop oxycode-bot
```

### Vercel Monitoring

- Visit Vercel Dashboard
- Go to your project
- Check Functions tab for logs
- Monitor analytics

---

## 🔄 Updates

### VPS Updates

```bash
# SSH to VPS
ssh root@YOUR_VPS_IP

# Navigate to project
cd /opt/oxycode-bot

# Pull latest changes
git pull origin main

# Install dependencies
npm install

# Build
npm run build

# Restart with PM2
pm2 restart oxycode-bot
```

### Vercel Updates

```bash
# Push to git
git push origin main

# Vercel auto-deploys
# Or manual deploy
vercel --prod
```

---

## 🐛 Troubleshooting

### VPS Issues

```bash
# Check PM2 status
pm2 status

# View error logs
pm2 logs oxycode-bot --err

# Check disk space
df -h

# Check memory
free -m

# Check processes
top
```

### Vercel Issues

- Check Vercel Dashboard for errors
- Review function logs
- Verify environment variables
- Check build logs

---

## 🔒 Security Notes

1. **Never commit .env files**
2. **Use strong JWT secrets**
3. **Enable HTTPS**
4. **Set up proper CORS**
5. **Regular security updates**

---

## 📞 Support

For issues:
1. Check logs
2. Review documentation
3. Open GitHub issue
4. Contact support

---

**Last Updated:** August 27, 2026
