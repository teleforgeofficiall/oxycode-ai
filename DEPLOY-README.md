# OXYCODE AI BOT - Deployment

## 🚀 Quick Start

### Option 1: VPS Deployment

```bash
# Connect to VPS
ssh root@YOUR_VPS_IP

# Password: $VPS_PASSWORD (use SSH key auth)

# Clone and setup
cd /opt
git clone https://github.com/your-username/oxycode-bot.git
cd oxycode-bot
npm install
npm run build

# Start with PM2
pm2 start npm --name "oxycode-bot" -- start
pm2 save
pm2 startup
```

### Option 2: Vercel Deployment

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
vercel --prod
```

### Option 3: Quick Deploy Script

```bash
# Windows
deploy.bat

# Or run Python script directly
python deploy-vps.py
```

---

## 📋 Prerequisites

### VPS
- Ubuntu 22.04
- Node.js 20+
- PM2
- SSH access

### Vercel
- Vercel account
- Node.js
- Git repository

---

## 🔧 Environment Variables

Create `.env` file:

```env
OPENAI_API_KEY=your_key
CLOUDFLARE_API_TOKEN=your_token
CLOUDFLARE_ACCOUNT_ID=your_account_id
DATABASE_URL=your_database_url
JWT_SECRET=your_jwt_secret
```

---

## 📊 Monitoring

### VPS
```bash
pm2 status
pm2 logs oxycode-bot
pm2 monit
```

### Vercel
- Dashboard: https://vercel.com/dashboard
- Functions tab for logs
- Analytics for usage

---

## 🔄 Updates

### VPS
```bash
cd /opt/oxycode-bot
git pull
npm install
npm run build
pm2 restart oxycode-bot
```

### Vercel
```bash
git push origin main
# Auto-deploys
```

---

## 🐛 Troubleshooting

### VPS
```bash
pm2 logs oxycode-bot --err
pm2 status
df -h
free -m
```

### Vercel
- Check Dashboard for errors
- Review function logs
- Verify env variables

---

## 📞 Support

- Check logs first
- Review documentation
- Open GitHub issue

---

**Status:** Ready for deployment
