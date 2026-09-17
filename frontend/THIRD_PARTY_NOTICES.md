# UI components

`src/components/ui/ActionButton.jsx` and the shimmer/hover styles in
`src/styles/modern.css` adapt Magic UI components listed on 21st.dev:

- [Shimmer Button on 21st.dev](https://21st.dev/community/components/explore/shimmer-button)
- [Interactive Hover Button on 21st.dev](https://21st.dev/community/components/explore/hover-dev)
- [Original Shimmer Button](https://github.com/magicuidesign/magicui/blob/main/apps/www/registry/magicui/shimmer-button.tsx)
- [Original Interactive Hover Button](https://github.com/magicuidesign/magicui/blob/main/apps/www/registry/magicui/interactive-hover-button.tsx)

Adaptations use plain JavaScript and CSS, the app's theme variables, native button
semantics, keyboard focus feedback and reduced-motion preferences. No Tailwind or
animation runtime is required. Remaining controls and layout styles are local.

## Magic UI licence

MIT License

Copyright (c) Magic UI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
