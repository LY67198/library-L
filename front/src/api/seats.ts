import { apiGet, apiPost } from './client'

export interface SeatItem {
  seat_id: string
  floor_id: number
  floor_name: string
  zone_id: number
  zone_name: string
  seat_number: string
  status: string
  booked_by_me: boolean
}

export function fetchSeats(params: {
  floor_id?: number; zone_id?: number; date?: string; slot?: string
}): Promise<{ seats: SeatItem[] }> {
  const q: Record<string, string> = {}
  if (params.floor_id != null) q.floor_id = String(params.floor_id)
  if (params.zone_id != null) q.zone_id = String(params.zone_id)
  if (params.date) q.date = params.date
  if (params.slot) q.slot = params.slot
  return apiGet('/seats', q)
}

export function bookSeat(seatId: string, date: string, slot: string) {
  return apiPost<{
    appointment_id: string; seat_id: string; floor_name: string
    zone_name: string; seat_number: string; date: string; slot: string
  }>(`/seats/${seatId}/book`, { date, slot })
}
