const currency = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
  signDisplay: 'exceptZero',
});

export function pounds(pence) {
  return currency.format(pence / 100);
}

export function unitValue(pence) {
  return pence === 100 ? '£1' : `${pence}p`;
}
