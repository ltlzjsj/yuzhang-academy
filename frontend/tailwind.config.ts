import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // yzsfxy 豫章书院 主色：藏青 + 金，深色顶栏/页脚、文化门户观感
        brand: {
          navy: '#2C3E50',
          navyDeep: '#1F2D3A',
          navySoft: '#34495E',
          blue: '#153F82',
          gold: '#EDB74F',
          goldDeep: '#C69A4B',
          goldSoft: '#F6D998',
          red: '#E74C3C',
          redDeep: '#C0392B',
          ink: '#1F2937',
          sub: '#555555',
          muted: '#8A94A0',
          bg: '#F4F5F3',
          panel: '#FFFFFF',
          line: '#E5E7EB',
        },
        // 既有 chat / kb 组件沿用 claude-* 令牌：重映射为新的浅色中性主题，
        // 让旧组件自动获得统一的「白卡片 + 浅灰底 + 藏青强调」观感，无需逐处改类名。
        claude: {
          bg: '#F4F5F3',
          panel: '#FFFFFF',
          border: '#E5E7EB',
          ink: '#1F2937',
          muted: '#6B7280',
          accent: '#2C3E50',
          accentHover: '#1F2D3A',
          bubbleUser: '#E8EEF4',
          bubbleAssistant: '#FFFFFF',
        },
      },
      fontFamily: {
        sans: ['"Microsoft YaHei"', '"PingFang SC"', '"Hiragino Sans GB"', 'Arial', 'sans-serif'],
        serif: ['STKaiti', 'KaiTi', '"STXingkai"', '"Noto Serif SC"', 'Georgia', 'serif'],
      },
      borderRadius: {
        bubble: '16px',
        card: '16px',
      },
      boxShadow: {
        soft: '0 1px 2px rgba(20,30,40,0.04), 0 6px 18px rgba(20,30,40,0.06)',
        lift: '0 18px 44px rgba(20,30,40,0.14)',
        nav: '0 2px 18px rgba(20,30,40,0.18)',
      },
      transitionTimingFunction: {
        claude: 'cubic-bezier(0.22, 1, 0.36, 1)',
        brand: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      maxWidth: {
        shell: '1200px',
      },
    },
  },
  plugins: [],
} satisfies Config
