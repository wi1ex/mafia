import logo from '@/assets/svg/iconLogo.svg'
import { ROULETTE_DAYS, rouletteAngle, rouletteDaysWord, validRouletteDays } from '@/services/subscriptionRoulette'

export async function createRouletteShareImage(days: number): Promise<File> {
  if (!validRouletteDays(days)) throw new Error('Invalid subscription roulette result')
  await Promise.all([
    document.fonts.load('500 144px Involve-Medium', String(days)),
    document.fonts.load('500 32px Involve-Medium', 'Удача на моей стороне'),
    document.fonts.load('500 24px Hauora-Medium', 'дней подписки в подарок'),
  ])
  const mark = new Image()
  mark.src = logo
  await mark.decode()

  const canvas = document.createElement('canvas')
  canvas.width = 1000
  canvas.height = 530
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas is unavailable')

  const purple = '#171723'
  const rim = '#2d2d46'
  const muted = '#44446a'
  const mint = '#00cd9b'
  const green = '#007b5d'
  ctx.fillStyle = '#f1f1f1'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  ctx.fillStyle = green
  ctx.font = '500 18px Hauora-Medium, sans-serif'
  ctx.fillText('РУЛЕТКА ПОДПИСКИ', 54, 65)
  ctx.fillStyle = purple
  ctx.font = '500 34px Involve-Medium, sans-serif'
  ctx.fillText('Удача на моей стороне', 54, 118)

  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.roundRect(36, 154, 506, 298, 28)
  ctx.fill()
  ctx.fillStyle = muted
  ctx.font = '500 22px Hauora-Medium, sans-serif'
  ctx.fillText('Мой выигрыш', 66, 204)
  ctx.fillStyle = green
  ctx.font = '500 144px Involve-Medium, sans-serif'
  ctx.fillText(String(days), 60, 348)
  const numberWidth = ctx.measureText(String(days)).width
  ctx.font = '500 46px Involve-Medium, sans-serif'
  ctx.fillText(rouletteDaysWord(days), 76 + numberWidth, 348)
  ctx.fillStyle = muted
  ctx.font = '500 26px Hauora-Medium, sans-serif'
  ctx.fillText('подписки в подарок', 66, 404)

  ctx.save()
  ctx.translate(762, 295)
  ctx.strokeStyle = '#dedee9'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.arc(0, 0, 200, 0, Math.PI * 2)
  ctx.stroke()
  ctx.fillStyle = rim
  ctx.beginPath()
  ctx.arc(0, 0, 176, 0, Math.PI * 2)
  ctx.fill()
  const rotation = rouletteAngle(days) % 360
  ROULETTE_DAYS.forEach((value, index) => {
    const angle = (-90 + index * 12 + rotation) * Math.PI / 180
    ctx.fillStyle = index % 2 ? '#ca342e' : '#171717'
    ctx.beginPath()
    ctx.moveTo(0, 0)
    ctx.arc(0, 0, 162, angle - Math.PI / 30, angle + Math.PI / 30)
    ctx.closePath()
    ctx.fill()
    ctx.save()
    ctx.rotate(angle + Math.PI / 2)
    ctx.fillStyle = '#ffffff'
    ctx.font = '500 16px Hauora-Medium, sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(String(value), 0, -137)
    ctx.fillStyle = '#8d8dc0'
    ctx.beginPath()
    ctx.arc(0, -170, 1.7, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  })
  ctx.strokeStyle = '#c6c6df66'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.arc(0, 0, 112, 0, Math.PI * 2)
  ctx.stroke()
  ctx.fillStyle = rim
  ctx.strokeStyle = '#5a5a8d'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.arc(0, 0, 48, 0, Math.PI * 2)
  ctx.fill()
  ctx.stroke()
  ctx.drawImage(mark, -38, -12.5, 76, 25)
  ctx.fillStyle = rim
  ctx.beginPath()
  ctx.moveTo(-11, -178)
  ctx.lineTo(11, -178)
  ctx.lineTo(0, -148)
  ctx.closePath()
  ctx.fill()
  ctx.restore()

  const pieces = [[575, 128], [936, 118], [563, 420], [938, 450], [696, 77], [861, 492], [624, 477], [962, 269]]
  pieces.forEach(([x, y], index) => {
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(index * 0.7)
    ctx.fillStyle = [mint, '#ca342e', rim, '#8d8dc0'][index % 4]
    ctx.beginPath()
    ctx.roundRect(-4, -8, 8, index % 2 ? 10 : 16, 2)
    ctx.fill()
    ctx.restore()
  })
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(value => value ? resolve(value) : reject(new Error('Could not render roulette image')), 'image/png')
  })
  return new File([blob], `roulette-${days}-days.png`, { type: 'image/png' })
}
