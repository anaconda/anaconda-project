/**
 * Seed questions.
 *
 * Source: Todd Caponi, "Sales Meetings: The Purpose, and My Top 30
 * Ice-Breaker Questions" — https://toddcaponi.com/sales-meetings-the-purpose-and-my-top-30-ice-breaker-questions/
 * Kept in the article's order. Attribution is repeated in the UI footer.
 */
export const CLASSIC_QUESTIONS = [
  "Who is the most famous person you've ever met?",
  'What is your Uber rating?',
  'Describe your closet.',
  'What is your favorite not-so-obvious social media follow?',
  'Describe your first car.',
  'What was the first concert you ever attended?',
  'What was your first paying job?',
  'What is/was your nickname, and why?',
  'What would you name your yacht?',
  'Who has been the most helpful person to you during your time here?',
  'What is your middle name? Why (if you know)?',
  'What is your biggest pet peeve? (the less obvious, the better)',
  'What is your least favorite word?',
  'What television show do you wish was still being made?',
  'What is the weirdest gift you\u2019ve ever received?',
  'What is your go-to candy?',
  'Who is your celebrity twin?',
  'As a kid, what did you want to be when you grew up?',
  'What is the first song on your favorite playlist?',
  'What is your favorite quote or mantra?',
  'What is a talent others have that you wish you had?',
  'What is a tip you would give your younger self?',
  'What is your not-so-obvious favorite app on your phone?',
  'What was your best and your worst subject in school?',
  'Who was your childhood hero?',
  'What is your favorite cause or charity?',
  'What has been the highlight and lowlight for you so far this year?',
  'If you could have any living celebrity over for dinner, who would it be?',
  'If you were forced to do karaoke but could choose the song, what would it be?',
  'What is one thing about you people would be surprised to learn?',
];

export const CROWDSOURCED_QUESTIONS = [
  'What non-food, non-drink item would you have to have if you were stranded on an island?',
  'What are your top 3 binge-worthy streaming shows?',
  'What was your first screen name?',
  "What's something you're grateful for, personally or professionally?",
  'Can you ride a horse?',
  'Show us how you tie your shoes and tell us why you tie them that way.',
];

/** @returns {Array<{text: string, category: 'classic'|'crowdsourced', createdBy: string}>} */
export function seedQuestions() {
  return [
    ...CLASSIC_QUESTIONS.map((text) => ({
      text,
      category: 'classic',
      createdBy: 'Todd Caponi',
    })),
    ...CROWDSOURCED_QUESTIONS.map((text) => ({
      text,
      category: 'crowdsourced',
      createdBy: 'Team',
    })),
  ];
}
