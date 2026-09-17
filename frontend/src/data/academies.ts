export interface Poem {
  title: string
  text: string
}

export interface Academy {
  id: string
  name: string
  city: string
  era: string
  summary: string
  history: string[]
  figures: string[]
  poems: Poem[]
  image: string
  narration: string
}

function thumb(src: string, w = 900, h = 675) {
  return '/api/v1/assets/thumb/academy/' + src.split('/').map(encodeURIComponent).join('/') + `?w=${w}&h=${h}`
}

export const ACADEMIES: Academy[] = [
  {
    id: 'bailudong',
    name: '白鹿洞书院',
    city: '九江市',
    era: '南唐 · 海内第一书院',
    summary: '位于庐山五老峰南麓，被誉为“海内第一书院”。朱熹重兴并亲订《白鹿洞书院揭示》，影响东亚书院制度。',
    history: ['南唐始建，北宋列名天下四大书院', '南宋朱熹重兴，订立学规', '明清屡修，讲学不辍'],
    figures: ['朱熹', '陆九渊', '王阳明'],
    poems: [{ title: '观书有感', text: '问渠那得清如许？为有源头活水来。' }],
    image: thumb('组织拍摄了江西遗存书院/江西四大书院/白鹿洞书院/白鹿洞书院正学之门前古牌坊.JPG'),
    narration: '白鹿洞书院位于庐山五老峰南麓，是海内第一书院。南宋朱熹在此重兴讲学，并亲订《白鹿洞书院揭示》，其“为学之序”影响深远。',
  },
  {
    id: 'ehu',
    name: '鹅湖书院',
    city: '上饶市',
    era: '南宋 · 朱陆论道之地',
    summary: '位于铅山鹅湖山麓，因朱熹与陆九渊“鹅湖之会”而名垂史册，是宋明理学史上标志性的论辩现场。',
    history: ['南宋淳熙二年朱陆鹅湖之会', '后建书院以祀并讲学', '历代修葺，遗存至今'],
    figures: ['朱熹', '陆九渊', '吕祖谦'],
    poems: [{ title: '鹅湖之会', text: '朱陆异同，千古论辩。' }],
    image: thumb('组织拍摄了江西遗存书院/江西四大书院/鹅湖书院/鹅湖书院全景图.jpg'),
    narration: '鹅湖书院因南宋朱熹与陆九渊的鹅湖之会而闻名。吕祖谦邀朱陆相会，就“尊德性”与“道问学”展开论辩，成为理学史上一段佳话。',
  },
  {
    id: 'xiangshan',
    name: '象山书院',
    city: '鹰潭市',
    era: '南宋 · 心学发祥之所',
    summary: '位于贵溪，陆九渊在此讲学，倡“心即理”“发明本心”，是陆王心学的重要发祥地。',
    history: ['陆九渊于象山精舍讲学', '门人建书院以传心学', '后世追祀，遗存犹在'],
    figures: ['陆九渊', '王阳明'],
    poems: [{ title: '陆九渊语', text: '宇宙便是吾心，吾心即是宇宙。' }],
    image: thumb('组织拍摄了江西遗存书院/江西四大书院/象山书院/象山书院遗址全景.JPG'),
    narration: '象山书院位于贵溪，是陆九渊讲学的心学发祥之地。他主张心即理、发明本心，其思想后来由王阳明发扬光大。',
  },
  {
    id: 'bailuzhou',
    name: '白鹭洲书院',
    city: '吉安市',
    era: '南宋 · 文章节义之邦',
    summary: '坐落于吉安白鹭洲上，是庐陵“文章节义”精神的象征，文天祥曾就读于此。',
    history: ['南宋建院于白鹭洲', '文天祥就读并高中', '历代弦歌不绝'],
    figures: ['文天祥', '江万里'],
    poems: [{ title: '过零丁洋', text: '人生自古谁无死，留取丹心照汗青。' }],
    image: thumb('组织拍摄了江西遗存书院/江西四大书院/白鹭洲书院/白鹭洲书院风月楼.JPG'),
    narration: '白鹭洲书院位于吉安白鹭洲上，是庐陵文章节义精神的象征。民族英雄文天祥曾在此读书，其“留取丹心照汗青”激励后世。',
  },
  {
    id: 'yuzhang',
    name: '豫章书院',
    city: '南昌市',
    era: '宋明 · 省会文教重镇',
    summary: '坐落于省会南昌，承宋明讲学之统、育江右人文之盛，是江西书院文化的地标。',
    history: ['南宋讲学之风渐盛', '明清渐入官学体系', '成为省会文教重镇'],
    figures: ['朱熹', '王阳明'],
    poems: [{ title: '豫章书院', text: '承千年讲学，启数智新生。' }],
    image: '',
    narration: '豫章书院坐落于江西南昌，承宋明讲学之统，育江右人文之盛，是江西书院文化的重要地标。',
  },
  {
    id: 'hualin',
    name: '华林书院',
    city: '宜春市',
    era: '北宋 · 民间兴学',
    summary: '位于奉新，北宋胡仲尧倾家兴办，藏书延师、广纳寒士，开江西民间书院兴学之风。',
    history: ['胡仲尧兴办华林书院', '藏书延师、广纳寒士', '开民间书院兴学之风'],
    figures: ['胡仲尧'],
    poems: [{ title: '华林兴学', text: '藏书延师，广纳寒士。' }],
    image: '',
    narration: '华林书院位于宜春奉新，北宋胡仲尧倾家兴办，藏书延师、广纳寒士，是江西民间书院兴学的代表。',
  },
  {
    id: 'aozhou',
    name: '鳌洲书院',
    city: '萍乡市',
    era: '明 · 萍乡名院',
    summary: '萍乡最著名的古代书院，明万历年间知县陆世勣始建，传承吴楚文化。',
    history: ['明万历年间始建', '历代重修', '传承吴楚文化'],
    figures: ['陆世勣'],
    poems: [{ title: '鳌洲书院', text: '萍水之畔，文脉绵延。' }],
    image: '',
    narration: '鳌洲书院是萍乡最著名的古代书院，始建于明代万历年间，历经重修，传承着吴楚地区的文教传统。',
  },
  {
    id: 'changxiang',
    name: '长芗书院',
    city: '景德镇市',
    era: '南宋 · 浮梁名院',
    summary: '位于浮梁（今景德镇），南宋庆元二年镇监李齐愈仿白鹿洞规制创建，有八百余年历史。',
    history: ['南宋庆元二年创建', '仿白鹿洞规制', '延续八百余年'],
    figures: ['李齐愈'],
    poems: [{ title: '长芗书院', text: '浮梁故地，长芗书香。' }],
    image: '',
    narration: '长芗书院位于景德镇浮梁，创建于南宋庆元二年，仿白鹿洞规制办学，已有八百余年历史。',
  },
]

export function academyById(id: string) {
  return ACADEMIES.find((a) => a.id === id)
}
