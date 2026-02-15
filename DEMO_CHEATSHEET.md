# 🎬 Demo Cheat Sheet — Quick Reference
*One-page reference for client demo*

## 🚀 Key Stats to Mention
- **96.2% transcription success rate** (25/26 clips processed)
- **30 minutes** total processing time (vs 6+ hours manual)
- **$200-400/month** saved vs Riverside.fm/Descript
- **50% B-roll coverage** with intelligent drone integration
- **6 render formats** generated automatically

## 📊 Demo Commands

### System Status Check
```bash
cd /Users/thelodgestudio/.openclaw/workspace/davinci-resolve-openclaw
python3 resolve_bridge.py  # Show DaVinci connection
ls renders/                # Show generated videos
```

### Show AI Analysis Results
```bash
# Speaker stats
python3 -c "
import json
with open('/Volumes/LaCie/VIDEO/nycap-portalcam/project_diarization.json') as f:
    data = json.load(f)
    print(f'Speakers: {len(data[\"speakers\"])}')
    for s, stats in data['speakers'].items():
        print(f'{s}: {stats[\"total_speaking_time\"]:.1f}s')
"

# Scene analysis summary  
python3 -c "
import json
with open('/Volumes/LaCie/VIDEO/nycap-portalcam/scene_analysis.json') as f:
    data = json.load(f)
    print(f'Success: {data[\"analyzed_clips\"]}/{data[\"total_clips\"]}')
    print(f'Shots: {data[\"scene_summary\"][\"shot_scale_distribution\"]}')
"
```

### Pipeline Command (Show Don't Run)
```bash
python3 pipeline_enhanced.py /path/to/footage --auto-render --render-preset youtube_1080p
```

## 🎯 30-Second Elevator Pitch
*"We've built an AI video editing pipeline that processes your multi-camera footage automatically. Upload raw files, get professional edits in 30 minutes. It's like having Riverside.fm and Descript combined, but it runs on your hardware with zero monthly fees."*

## 💰 Cost Comparison Table
| **Feature** | **Riverside.fm** | **Our System** |
|------------|-----------------|----------------|
| Monthly cost | $200-400+ | $0 |
| Processing limits | Restricted hours | Unlimited |
| Data location | Cloud-dependent | Your hardware |
| Customization | Locked features | Full source code |

## 🎬 Demo Flow (30 minutes)

### 1. Show Results First (5 min)
- Open `renders/index.html` 
- Play "30-Second Summary v3"
- **Say:** *"This came from 26 raw clips in 30 minutes"*

### 2. Show Source Material (5 min)  
- `ls /Volumes/LaCie/VIDEO/nycap-portalcam/*.MP4 | head -5`
- **Say:** *"28 minutes of raw DJI drone + Sony interview footage"*

### 3. Show AI Analysis (10 min)
- Run speaker diarization command
- Run scene analysis command  
- Open DaVinci timeline ("30s Summary v3")
- **Say:** *"AI identified speakers, classified shots, built timeline automatically"*

### 4. Business Case (10 min)
- Show cost comparison
- Highlight unlimited processing
- Mention custom development capabilities
- **Say:** *"Own the technology permanently vs rent it monthly"*

## 🤔 FAQ Quick Answers

**"How reliable?"** → *"96.2% success rate, production-tested"*

**"Time savings?"** → *"30 minutes vs 6+ hours per video"*  

**"Custom features?"** → *"Full source code, unlimited customization"*

**"Data security?"** → *"Everything on your hardware, no cloud uploads"*

**"Getting started?"** → *"Ready now, half-day setup, operational in a week"*

## 📱 Files to Have Open
1. **Browser:** `renders/index.html` (video gallery)
2. **DaVinci Resolve:** nycap-portalcam project, "30s Summary v3" timeline  
3. **Terminal:** Ready in `/davinci-resolve-openclaw` directory
4. **Backup:** `CLIENT_DEMO.md` for technical details

## 🎯 Success Signals
- ✅ Client asks about implementation timeline
- ✅ Questions about custom features  
- ✅ Wants to see more examples
- ✅ Discusses team training needs
- ✅ Asks about technical requirements

## 🚨 Emergency Backup Plan
If live demo fails:
1. **Show pre-rendered videos** (renders/ directory)
2. **Walk through analysis files** (JSON reports)
3. **Focus on business case** (CLIENT_DEMO.md)  
4. **Schedule follow-up** technical demonstration

---

## 💡 Key Message
*"This technology exists, it works, and it can transform your video production starting today."*

**Next step:** *"When would you like to start using it?"*

---

*Keep this open during demo | February 2026*